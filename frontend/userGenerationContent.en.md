1: 
2: # User Generated Content — Ratings & Comments (Design and Implementation)
3: 
4: This document systematically describes the project's current User Generated Content (UGC) functionality — primarily product ratings and product comments (comments / replies / likes). It intentionally ignores deprecated legacy logic (the old `reviews` table and related code) and only covers the currently active data structures, backend routes, and frontend presentation/interaction.
5: 
6: ## Overview
7: 
8: - Key features:
9:   - Ratings: Users can rate products they have purchased and whose orders are marked as `completed`. Each completed order can be used once as a rating quota for a given product.
10:   - Comments: Only users who have completed purchase of the product may post comments or replies (replies are only allowed as one-level replies to top-level comments).
11:   - Likes: Users can like comments (top-level or replies). Currently only liking is supported — there is no unlike endpoint.
12:   - Aggregated view: Product detail page shows rating statistics (average rating, number of ratings) and a comment tree (roots + replies) with sorting by likes or time.
13: 
14: Core files:
15: 
16: - Backend routes and logic: `backend/app/routers/reviews.py`
17: - Backend models: `backend/app/models.py`
18: - Database initialization (ensure review tables exist): `backend/app/db.py`
19: - Request/response schemas: `backend/app/schemas.py`
20: - Frontend presentation and interaction: `frontend/src/views/ProductDetail.vue`
21: - Frontend HTTP wrapper (auth handling): `frontend/src/api/http.ts`
22: 
23: All file references above are clickable paths.
24: 
25: ---
26: 
27: ## Data model (current)
28: 
29: The backend defines three primary tables via SQLAlchemy (see `backend/app/models.py`):
30: 
31: - `product_ratings` (model: `ProductRating`)
32:   - Columns: `id, user_id, product_id, order_id, rating, created_at`
33:   - Note: Records a product rating tied to an order; `order_id` enforces that the same order can only be used once to rate the same product.
34: 
35: - `product_comments` (model: `ProductComment`)
36:   - Columns: `id, user_id, product_id, parent_id, content, created_at, updated_at`
37:   - Note: Supports a tree shape but code only allows one-level replies: `parent_id` NULL indicates a root comment; replies point to a root comment's `id`.
38: 
39: - `product_comment_likes` (model: `ProductCommentLike`)
40:   - Columns: `id, user_id, comment_id, created_at`
41:   - Note: Records a user's like of a comment. There is currently no database-level unique constraint on `(user_id, comment_id)` — deduplication is enforced at the route layer by checking existence before insert.
42: 
43: These tables are created at application initialization if absent by `backend/app/db.py::_ensure_product_review_tables` (a lightweight SQLite self-migration approach for dev setups).
44: 
45: Note: The repository still contains an older `Review` model (in `backend/app/models.py`) related to legacy logic; this document intentionally ignores that `reviews` table and its old flows.
46: 
47: ---
48: 
49: ## Backend implementation highlights (behavior & routes)
50: 
51: Primary routes are implemented in `backend/app/routers/reviews.py`:
52: 
53: - `GET /api/products/{product_id}/reviews` — list view
54:   - Returns `ProductReviewPageOut` (contains `summary`, `ratings[]`, `comments[]`).
55:   - Functionality: computes average rating, rating count, comment count, the user's rating quota and eligible order ids (for rating dropdown), and serializes the comment tree (roots + replies). Each comment includes `like_count` and `liked_by_me` when applicable.
56:   - The endpoint can be called anonymously; `liked_by_me` is only set when the request is authenticated.
57: 
58: - `POST /api/products/{product_id}/ratings` — submit rating
59:   - Payload: `{ order_id: str, rating: int }` (1–5)
60:   - Permission: must be authenticated (`Depends(get_current_user)`).
61:   - Validation logic:
62:     1. Query `_eligible_order_ids` to find user's completed orders that contain the product (`status == 'completed'` and order items matching the product SKU → product_id).
63:     2. Calculate the available rating quota (`_rating_quota`) by subtracting already-used order_ids from eligible ones.
64:     3. Verify `payload.order_id` is within the available orders; otherwise reject.
65:     4. Insert a `ProductRating` record (storing `order_id` prevents duplicate ratings from the same order).
66: 
67: - `POST /api/products/{product_id}/comments` — create a new (top-level) comment
68:   - Payload: `{ content: string }`
69:   - Permission: must be authenticated and must have purchased the product (checked by `_can_comment` which uses `_eligible_order_ids`).
70: 
71: - `POST /api/products/{product_id}/comments/{comment_id}/replies` — reply to a top-level comment (only)
72:   - Permission: same as above (must have purchased the product).
73:   - Validation: only allowed when the parent comment is a top-level comment (`parent.parent_id is None`); multi-level nesting is disallowed.
74: 
75: - `POST /api/products/{product_id}/comments/{comment_id}/like` — like a comment
76:   - Permission: must be authenticated.
77:   - Implementation: check whether the current user already liked the comment; if present, return 400; otherwise insert a `ProductCommentLike` record and commit.
78: 
79: Implementation notes:
80: 
81: - Comment serialization (`_serialize_comments`) uses a three-step query approach:
82:   1. Query root comments (`parent_id IS NULL`) and order them as requested;
83:   2. Query replies for those root comments (ordered by time ascending);
84:   3. Aggregate `product_comment_likes` to compute each comment's `like_count`, and compute `liked_by_me` for the current user. This avoids N+1 queries but can still be heavy for products with many comments.
85: 
86: - Sorting options: `sort=likes|time`.
87:   - `time`: `created_at DESC, id DESC`.
88:   - `likes`: `like_count DESC, created_at DESC` (implemented with `GROUP BY` + `COUNT`).
89: 
90: ---
91: 
92: ## Frontend implementation (user interaction)
93: 
94: The main page is `frontend/src/views/ProductDetail.vue`:
95: 
96: - Presentation:
97:   - Top area shows average rating and rating count (`reviewSummary.average_rating`, `reviewSummary.rating_count`) rendered with `el-rate`.
98:   - A summary card shows average rating, comment count, and the user's rating quota.
99:   - Rating form: the user must select an available `order_id` (dropdown populated from `reviewSummary.available_rating_orders`) and choose a star rating before submitting.
100:   - Comment form: textarea to post comments.
101:   - Comment list: renders `comments` array; each comment shows author, time, content, like count, and reply action; replies are single-level.
102: 
103: - Frontend API flows (key functions):
104:   - `loadReviews()` calls `GET /api/products/{id}/reviews?sort=<likes|time>` and refreshes `reviewSummary`, `ratings`, and `comments`.
105:   - `submitRating()` calls `POST /api/products/{id}/ratings` with `{ order_id, rating }` and refreshes on success.
106:   - `submitComment()` calls `POST /api/products/{id}/comments` and refreshes on success.
107:   - `submitReply(commentId)` calls `POST /api/products/{id}/comments/{commentId}/replies` and refreshes on success.
108:   - `likeComment(commentId)` calls `POST /api/products/{id}/comments/{commentId}/like` and refreshes on success.
109: 
110: Frontend references: `frontend/src/views/ProductDetail.vue` and the generic HTTP wrapper `frontend/src/api/http.ts` (handles JWT and 401/403 redirects).
111: 
112: ---
113: 
114: ## Business rules (itemized)
115: 
116: 1. Rating eligibility & quota
117:    - Only users with completed orders containing the product (`status == 'completed'`) are eligible to rate.
118:    - Each completed order can be used once to rate the same product. Once an `order_id` is used for a rating, it is removed from the available quota (`_rating_quota`).
119:    - Rating values are limited to the 1–5 range.
120: 
121: 2. Comment eligibility
122:    - Only users who have purchased and completed the product are allowed to post comments or replies.
123:    - Comments are not bound to an `order_id` (unlike ratings); thus eligible users can post multiple comments unless additional business rules are applied.
124: 
125: 3. Reply rules
126:    - Only replies to top-level comments are supported (the parent must be root), preventing unlimited nesting.
127:    - This keeps the UI simpler and reduces abuse vectors.
128: 
129: 4. Like rules
130:    - Both frontend and backend check for duplicate likes; the backend returns 400 on duplicate like attempts.
131:    - There is currently no unlike endpoint; if needed, implement a `DELETE` or `POST /unlike` endpoint.
132: 
133: 5. Comment sorting
134:    - Clients can request sorting by `likes` (descending by like count) or `time` (descending by creation time) via the `sort` parameter.
135: 
136: ---
137: 
138: ## API contract (example)
139: 
140: GET /api/products/{product_id}/reviews  -> 200 OK
141: 
142: ```json
143: {
144:   "summary": {
145:     "average_rating": 4.5,
146:     "rating_count": 12,
147:     "comment_count": 5,
148:     "my_rating_quota": 1,
149:     "can_comment": true,
150:     "available_rating_orders": ["202604120001"]
151:   },
152:   "ratings": [ { "id": 1, "user_id": 2, "product_id": 10, "order_id": "202604120001", "rating": 5, "created_at": "..." } ],
153:   "comments": [
154:     {
155:       "id": 11,
156:       "user_id": 3,
157:       "user_name": "Alice",
158:       "product_id": 10,
159:       "parent_id": null,
160:       "content": "Great book",
161:       "created_at":"...",
162:       "updated_at":"...",
163:       "like_count": 2,
164:       "liked_by_me": false,
165:       "replies": [ { "id": 12, "user_id": 4, "user_name":"Bob", "content":"Agreed" , "like_count":0 } ]
166:     }
167:   ]
168: }
169: ```
170: 
171: POST /api/products/{product_id}/ratings
172: 
173: ```json
174: // body
175: { "order_id": "202604120001", "rating": 5 }
176: 
177: // success -> returns created rating record
178: ```
179: 
180: POST /api/products/{product_id}/comments
181: 
182: ```json
183: // body
184: { "content": "This is my comment" }
185: 
186: // success -> created comment object
187: ```
188: 
189: POST /api/products/{product_id}/comments/{comment_id}/like
190: 
191: ```json
192: // no body; returns { "message": "like success" }
193: ```
194: 
195: (Refer to `backend/app/schemas.py` for the exact Pydantic response models and field names.)
196: 
197: ---
198: 
199: ## Security, validation, and dependencies
200: 
201: - Authentication: write operations (ratings/comments/replies/likes) depend on `get_current_user` and require a valid JWT. See `backend/app/deps.py` for implementation.
202: - Read endpoint: `GET /reviews` supports optional authentication (`get_current_user_optional`) so that `liked_by_me` can be populated when available.
203: - Input validation: request payloads are validated by Pydantic schemas in `backend/app/schemas.py` (e.g., `RatingCreate`, `CommentCreate`), with additional business validation performed in routes (quota checks, order ownership, parent_id checks, etc.).
204: 
205: ---
206: 
207: ## Known limitations & improvement suggestions
208: 
209: 1. Concurrency & duplicate likes: the route-level existence check prevents duplicate likes but is vulnerable to race conditions under high concurrency. Add a DB-level unique constraint:
210: 
211:    - Add a unique index on `(user_id, comment_id)` in `product_comment_likes` and handle `IntegrityError` on insert to provide transactional guarantees.
212: 
213: 2. Performance for comments/likes: `_serialize_comments` runs multiple queries (roots → replies → like aggregates → liked_by_me). For high-traffic or high-comment-volume products consider:
214: 
215:    - Caching aggregated counters (`comment_count`, `like_count`) in the `product` table or a dedicated stats table and update via triggers or async tasks;
216:    - Adding indexes on `product_comments.product_id` and `product_comment_likes.comment_id`;
217:    - Introducing pagination for root comments to avoid loading all comments at once.
218: 
219: 3. Abuse and moderation: there is no automated or manual moderation workflow. Consider adding:
220: 
221:    - Automated content checks (sensitive words, spam detection) and a manual review workflow;
222:    - A report endpoint and admin delete/hide endpoints;
223:    - Audit logs for comment moderation actions.
224: 
225: 4. UX improvements:
226: 
227:    - Add an unlike endpoint (UNLIKE);
228:    - Optionally bind comments to `order_id` for stronger proof (currently comments are not tied to an order).
229: 
230: ---
231: 
232: ## Local testing & debugging
233: 
234: 1. Start the backend and ensure the DB is initialized (`backend/app/db.py::init_db` creates `product_ratings` / `product_comments` / `product_comment_likes`).
235: 2. Create a completed order for a demo user (or use helper functions in `backend/app/seed.py`) to obtain `order_id` values eligible for rating.
236: 3. The frontend `ProductDetail.vue` automatically loads `/api/products/{id}/reviews` and renders the ratings/comments; use browser devtools or curl to exercise the API.
237: 
238: Example curl:
239: 
240: ```bash
241: # View reviews and ratings
242: curl "http://localhost:8001/api/products/10/reviews"
243: 
244: # Submit a rating (requires Authorization: Bearer <JWT>)
245: curl -X POST -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
246:   -d '{"order_id":"202604120001","rating":5}' \
247:   http://localhost:8001/api/products/10/ratings
248: 
249: # Submit a comment
250: curl -X POST -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
251:   -d '{"content":"Great!"}' \
252:   http://localhost:8001/api/products/10/comments
253: ```
254: 
255: ---
256: 
257: ## Reference code locations
258: 
259: - Backend models & table initialization: `backend/app/models.py`, `backend/app/db.py`
260: - Backend routes & implementation: `backend/app/routers/reviews.py`
261: - Request & response schemas: `backend/app/schemas.py`
262: - Frontend main implementation: `frontend/src/views/ProductDetail.vue`
263: - Frontend HTTP wrapper (auth & error handling): `frontend/src/api/http.ts`
264: 
265: ---
266: 
267: This document summarizes the current design and implementation of the project's user generated content (ratings and comments). The legacy `reviews` table and its logic are intentionally omitted. If historical data migration or compatibility is required, plan a dedicated migration path and compatibility layer.
