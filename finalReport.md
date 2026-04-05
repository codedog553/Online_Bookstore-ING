# Chapter 1 Introduction

## 1.1 Project Background

The rapid growth of online retail has made bookstore systems a representative case for studying modern web application design. Compared with a simple catalogue website, an online bookstore integrates multiple concerns, including account management, product discovery, configurable stock-keeping units (SKUs), shopping-cart operations, order processing, administration, multilingual interfaces, and data consistency. For a software engineering project, such a domain is particularly useful because it combines both conventional information system requirements and dynamic user interaction requirements.

This project develops a local-run online bookstore system that is intended for coursework demonstration rather than production deployment. The system is designed to be functionally complete, structurally explainable, and traceable to requirement identifiers. In addition to conventional e-commerce features, the project introduces an intelligent agent microservice based on the DeepSeek official API. This agent is used to support natural-language book enquiry, recommendation, and confirmation-driven shopping-cart operations while preserving strict control over writable data access.

The final system therefore serves two purposes. First, it acts as a complete bookstore prototype covering customer-side, vendor-side, and administration-side functions. Second, it acts as a coherent case study for software engineering documentation, including requirements analysis, architectural design, database design, dynamic modelling, software quality, and further work.

## 1.2 Project Objectives

The project is built with the following objectives:

1. To implement an end-to-end online bookstore workflow including registration, browsing, searching, shopping-cart management, checkout, order tracking, and vendor-side product and order management.
2. To support configurable products through SKU-level options, stock quantities, availability states, and multi-image management.
3. To support multilingual interaction in both user interface texts and product information presentation.
4. To introduce an intelligent agent layer that can understand natural language, search the local catalogue, recommend books, and safely trigger shopping-cart operations through explicit confirmation.
5. To produce a system with a sufficiently complete design so that it can be used as the basis of a formal software engineering report.

## 1.3 Project Scope

The project is explicitly scoped as a coursework system. It is intended to run locally, and therefore the design priorities differ from those of a production system.

- The system does not aim to optimize for large-scale deployment or high concurrency.
- The main focus is on correctness, design clarity, feature traceability, and demonstrability.
- The system uses SQLite by default for ease of local setup, but the data model and service layering are designed to be extensible to PostgreSQL.
- The intelligent agent is restricted to read-only catalogue access and shopping-cart CRUD, and is deliberately prevented from interacting with payment, checkout finalization, or administrative capabilities.

## 1.4 Technology Overview

The system is composed of three major implementation layers:

- **Backend**: FastAPI + SQLAlchemy + SQLite
- **Frontend**: Vue 3 + Vite + Element Plus + Pinia + vue-i18n
- **Agent Microservice**: FastAPI + DeepSeek API + controlled repository layer

At a high level, the frontend communicates with the main backend for normal business functions such as product browsing, checkout, and order management. For natural-language conversation and agent-driven shopping-cart operations, the frontend communicates with the dedicated `agentserver` microservice.

---

# Chapter 3 Requirements Analysis

## 3.1 Functional Requirements Overview

The system requirements are divided into customer-side functions, vendor/admin-side functions, product and SKU extensions, order-processing extensions, and multilingual support. The implemented system follows the coursework requirement numbering scheme and can be traced back to those requirement identifiers.

### 3.1.1 Customer-Side Requirements

The customer-facing functions include:

- user registration with name, email, password, and shipping address;
- unauthenticated browsing of product lists and product details;
- authenticated access to cart, checkout, and order features;
- product search by title;
- long-list navigation with pagination;
- product details with author, publisher, and description;
- shopping-cart add, update, remove, and list operations;
- checkout and order placement;
- order list and order detail pages;
- order status transition handling, including cancel and confirm receipt.

### 3.1.2 Vendor/Admin Requirements

The management-side functions include:

- product browsing and searching;
- product creation and editing;
- SKU-level configuration management;
- upload and deletion of SKU-specific multiple images;
- product activation/deactivation;
- order browsing and order detail inspection;
- order status updates such as shipping and vendor-side cancellation.

### 3.1.3 Product and Inventory Requirements

The system models each sellable configuration as a SKU. A product may have one or more options, and each option combination is represented by an individual SKU with:

- separate stock quantity;
- separate availability flag;
- separate associated photo set.

This enables the system to support multiple editions of the same book, such as paperback and hardcover, and to keep stock validation accurate during cart updates and order placement.

### 3.1.4 Internationalization Requirements

The project supports multilingual user interface content and bilingual product information:

- user interface labels are provided through `vue-i18n` resource files;
- product information is stored in both Chinese and English fields;
- display logic determines whether Chinese or English content is shown depending on the selected locale.

### 3.1.5 Intelligent Agent Requirements

The agent subsystem adds a new interaction style on top of the bookstore system. The agent must:

- conduct multi-turn conversations with users;
- understand natural-language requests about books;
- query the local catalogue through restricted read-only access;
- return recommendation and information responses grounded in local database content;
- support shopping-cart add, update, remove, and list operations for the current session user only;
- generate confirmation prompts before any cart modification;
- avoid access to payment, administrative, and sensitive user capabilities.

## 3.2 Non-Functional Requirements

In addition to the functional requirements, several non-functional requirements strongly shape the design.

### 3.2.1 Correctness and Traceability

The system must implement requirements in a traceable manner so that features can be verified against requirement identifiers and code locations. This is particularly important for coursework evaluation.

### 3.2.2 Security

The system must prevent unauthorized access, avoid cross-user data leakage, protect shopping-cart write operations from forgery and replay, and mitigate common web risks such as XSS and CSRF.

### 3.2.3 Usability

The system must remain usable for ordinary customers and administrators. This includes readable interfaces, multilingual text, mobile-friendly layouts, and clear confirmation dialogs for destructive or state-changing operations.

### 3.2.4 Maintainability and Extensibility

The codebase should allow later enhancement of recommendation logic, reporting, database migration, and further agent skills without major redesign.

### 3.2.5 Local Operability

Since the project is designed to run locally, setup and execution should remain straightforward. Seed scripts and a small default dataset help ensure predictable testing and demonstration.

## 3.3 Key Use Cases

The most important use cases in the system are listed below.

### 3.3.1 Customer Purchases a Book

1. The customer browses or searches for a book.
2. The customer opens the product detail page.
3. The customer selects a valid SKU configuration.
4. The customer adds the item to the cart.
5. The customer adjusts quantity or removes items if needed.
6. The customer proceeds to checkout.
7. The system validates stock and availability.
8. The system creates an order and clears the purchased cart items.

### 3.3.2 Vendor Maintains Product Data

1. The vendor accesses the admin product page.
2. The vendor searches or selects a product.
3. The vendor edits product metadata, creates SKUs, adjusts stock, or uploads SKU images.
4. The system persists the changes and reflects them on the frontend catalogue.

### 3.3.3 Customer Uses the Intelligent Agent

1. The customer opens the agent assistant drawer.
2. The customer asks for a recommendation or book information.
3. The agent identifies the intent and may consult the local catalogue.
4. The agent responds naturally using database-grounded information.
5. If the user expresses a cart operation intent, the agent generates a structured action suggestion.
6. The frontend shows a confirmation dialog.
7. Only after confirmation does the agent microservice execute the cart CRUD operation for the current user.

## 3.4 Assumptions and Constraints

The implementation is based on the following assumptions:

- The system runs in a trusted local development environment.
- The DeepSeek API key is available when intelligent conversation is required.
- Only one primary database is used at runtime.
- The current implementation does not include payment settlement.
- The project prioritizes functional coverage and design explanation over production-grade scalability.

---

# Chapter 4 System Design

## 4.1 Architectural Design

### 4.1.1 High-Level Structure

The system adopts a layered, service-oriented architecture composed of a frontend, a main backend, an intelligent agent microservice, and a persistence layer.

```text
Vue Frontend
   ├─ normal page requests ───────────────> Backend FastAPI
   └─ natural-language interaction ───────> Agentserver FastAPI
                                                ├─ DeepSeek API
                                                └─ controlled DB access

Backend FastAPI + Agentserver FastAPI
                    └───────────────> SQLite / PostgreSQL + local uploads/
```

This architecture separates routine business operations from natural-language interaction logic. The separation improves clarity of responsibilities, strengthens security boundaries, and makes the agent subsystem easier to evolve independently.

### 4.1.2 Frontend Responsibilities

The frontend is responsible for:

- rendering product, cart, checkout, order, and admin pages;
- maintaining the user interaction flow;
- displaying multilingual UI content;
- calling backend APIs for standard business operations;
- calling the agent microservice for conversation and agent-driven cart actions;
- presenting confirmation dialogs for cart mutations generated through the agent.

### 4.1.3 Main Backend Responsibilities

The main backend acts as the principal business service. It is responsible for:

- authentication and authorization;
- product and SKU management;
- standard cart operations;
- checkout and order creation;
- order status updates and timeline generation;
- admin-side management features;
- image path management and static file exposure.

### 4.1.4 Agent Microservice Responsibilities

The agent microservice is introduced as a separate service to support natural-language interaction. It is responsible for:

- maintaining multi-turn chat context;
- invoking DeepSeek for language understanding and response generation;
- querying the local catalogue through read-only repository logic;
- identifying shopping-cart intents;
- generating confirmation text for cart actions;
- executing current-user cart CRUD only after frontend confirmation;
- enforcing strict separation from payment, admin, and sensitive-user functions.

### 4.1.5 Architectural Rationale

Several architectural decisions were made deliberately:

1. **Frontend/backend separation** keeps presentation concerns separate from business logic.
2. **Main backend/agentserver separation** avoids mixing LLM-related concerns into the core bookstore service.
3. **Repository-layer restriction** ensures that the agent cannot call arbitrary database functions.
4. **Dedicated confirmation flow** ensures that natural-language intent does not directly imply database mutation.
5. **Local file storage for images** keeps binary content outside the relational database.

## 4.2 Data Modelling

### 4.2.1 Core Relational Entities

The database is centred around the following entities:

- `users`
- `addresses`
- `categories`
- `products`
- `product_skus`
- `cart_items`
- `orders`
- `order_items`
- `order_status_events`

The design models product descriptions at the product level and sellable inventory at the SKU level. This allows one product to expose multiple configurations such as paperback and hardcover while maintaining separate stock and availability per SKU.

### 4.2.2 Main Relationships

- One user can own many addresses.
- One user can own many cart items.
- One category can contain many products.
- One product can contain many SKUs.
- One order belongs to one user and contains many order items.
- One order has many status events.
- Each cart item and each order item points to one SKU.

### 4.2.3 Storage of Structured and Unstructured Data

Relational data such as users, orders, and cart items are stored in the database. Image data is handled differently:

- product and SKU images are stored as files under `backend/app/uploads/sku_{id}/`;
- the database stores references and associated JSON-like metadata rather than image binaries;
- product-level option definitions and SKU option values are stored as JSON strings in `TEXT` fields for SQLite compatibility.

This design minimizes database bloat while retaining a clear mapping between relational entities and media assets.

### 4.2.4 Database Constraints and Integrity Rules

The design enforces several business integrity rules:

- a cart item belongs to one user only;
- a cart item must reference exactly one SKU;
- an order item records SKU configuration snapshot data at purchase time;
- address snapshots are persisted in the order record so that later address changes do not affect historical orders;
- unavailable or out-of-stock SKUs must not pass cart or checkout validation.

### 4.2.5 Indexing Strategy

The current implementation relies on primary keys, unique email indexing, and frequent foreign-key access paths. For future migration to PostgreSQL, the design recommends:

- full-text or trigram indexing on product titles;
- composite indexing on `(user_id, sku_id)` for cart items;
- composite indexing on `(user_id, created_at)` for orders;
- indexing on SKU availability and product association.

### 4.2.6 Migration Strategy

The current database runs on SQLite for convenience. The migration strategy is:

1. maintain schema through SQLAlchemy models;
2. initialize or rebuild local datasets via seed scripts;
3. introduce Alembic if the system is migrated to PostgreSQL;
4. convert JSON-like `TEXT` fields to native `JSONB` where suitable;
5. harden status and validation constraints in the database layer if productionization is required.

### 4.2.7 ER Diagram

```text
users 1 ─── n addresses
users 1 ─── n cart_items
categories 1 ─── n products
products 1 ─── n product_skus
users 1 ─── n orders
orders 1 ─── n order_items
orders 1 ─── n order_status_events
product_skus 1 ─── n cart_items
product_skus 1 ─── n order_items
```

The full text ER diagram is provided in the project README and can be directly reused in the final formatted document.

## 4.3 Dynamic Modelling

Dynamic modelling explains how the system changes over time in response to user operations and internal business events.

### 4.3.1 Order State Machine

The order subsystem uses the following states:

- `pending`
- `shipped`
- `completed`
- `cancelled`

The main transitions are:

- placing an order creates a `pending` order;
- vendor shipment changes `pending -> shipped`;
- customer confirmation changes `shipped -> completed`;
- customer or vendor cancellation changes `pending -> cancelled`;
- timeout logic also changes `pending -> cancelled`.

This state machine is supported by both a current-state field (`orders.status`) and an event history table (`order_status_events`).

### 4.3.2 Intelligent Cart Confirmation Flow

The agent-driven cart flow is another important dynamic behaviour.

```text
User message
   -> intent recognition
   -> optional catalogue/cart lookup
   -> action suggestion
   -> frontend confirmation dialog
   -> confirm or cancel
   -> database mutation or no change
```

The key rule is that natural-language understanding is not equivalent to immediate execution. Any cart write operation must pass through the explicit confirmation stage.

### 4.3.3 Conversation State Management

The agent maintains multi-turn context through a conversation store. Each conversation is bound to either:

- the authenticated user ID, or
- the anonymous client IP in non-authenticated mode.

This prevents context leakage and ensures that cart operations remain scoped to the current session user.

### 4.3.4 Failure and Exception Reactions

The system also changes state when validation fails. Examples include:

- an out-of-stock SKU preventing a cart update;
- invalid confirmation tokens preventing execution;
- session mismatch preventing conversation reuse;
- insufficient SKU information causing the agent to ask for clarification instead of mutating data.

## 4.4 API Design and Interaction Model

### 4.4.1 General API Style

The system uses REST-style JSON APIs. GraphQL is not used. This decision was made because:

- the resource model is stable and relatively clear;
- the project benefits from explicit, inspectable routes;
- REST integrates naturally with FastAPI and Swagger;
- the coursework context prioritizes explainability over API abstraction.

### 4.4.2 Main Backend API Groups

The main backend exposes endpoints for:

- authentication and addresses;
- products and product detail;
- standard cart operations;
- checkout and orders;
- admin product/order management.

Typical examples include:

- `GET /api/products`
- `GET /api/products/{id}`
- `GET /api/cart`
- `POST /api/orders`
- `GET /api/admin/products`

### 4.4.3 Agentserver API Groups

The agent microservice exposes:

- `POST /chat`
- `GET /cart`
- `POST /cart/add`
- `PUT /cart/update`
- `DELETE /cart/remove`
- `GET /csrf-token`

The interaction pattern is:

1. user sends a natural-language message to `/chat`;
2. the service returns natural-language reply and optional `action_suggestion`;
3. the frontend decides whether clarification, confirmation, or direct read-only display is needed;
4. any cart write is executed only after dialog confirmation.

### 4.4.4 Exception Handling

Error handling is based on HTTP status codes plus JSON response bodies. Common status codes include:

- `400` invalid request or business-rule violation;
- `401` unauthenticated;
- `403` forbidden or wrong conversation ownership;
- `404` missing resource;
- `409` confirmation or conflict issue;
- `422` validation failure;
- `500` internal server error.

This model allows the frontend to distinguish validation errors, permission problems, and execution failures clearly.

## 4.5 Special Design Topics

### 4.5.1 Mobile UX Design

Although the system is not primarily a mobile-first product, the frontend is designed to remain usable on mobile devices. Design considerations include:

- responsive layout widths;
- safe touch target sizes;
- larger confirmation dialogs for important cart operations;
- simplified drawer and dialog patterns for narrow screens.

The communication protocol remains JSON over REST, which is suitable for both mobile and desktop clients.

### 4.5.2 Search Engine Optimization

SEO is not a primary goal in a local coursework system, but the design still adopts stable and semantically meaningful URL patterns such as `/products/{id}`. Product pages contain structured content such as title, author, publisher, and description, which would help indexing if the system were later extended with SSR or pre-rendering.

### 4.5.3 Web Application Security

From a design perspective, the system addresses the following concerns:

- Bearer token authentication;
- CSRF protection for cart mutation endpoints;
- confirmation-token verification for write actions;
- restricted repository access in the agent layer;
- filtering of obviously unsafe user input;
- rate limiting for chat and cart endpoints;
- separation of agent authority from payment, checkout finalization, and admin operations.

### 4.5.4 Product Recommendation Design

The current recommendation strategy combines:

- rule-based keyword and theme matching;
- title, author, and description search;
- multi-turn conversational preference understanding through DeepSeek;
- natural-language response generation grounded in local catalogue data.

This design is deliberately lightweight and explainable, making it more appropriate for the dataset size and coursework scope than a heavy machine-learning recommendation pipeline.

### 4.5.5 Reports and Analytics Design

The current implementation preserves the data foundation required for future reporting, including:

- order totals;
- status timestamps;
- order items and SKU references;
- product-category links;
- user review and rating data.

Future reporting can therefore support sales ranking, status distribution, stock alerts, category-level statistics, and user behaviour summaries.

---

# Chapter 6 Software Quality

## 6.1 Software Verification

### 6.1.1 Verification Strategy

The verification strategy combines manual testing, automated API testing, and interactive debugging. This mixed approach is appropriate because the system contains both deterministic backend logic and complex user interaction flows that involve multilingual UI, confirmation dialogs, and agent-driven operations.

Testing responsibilities are naturally divided across the development team as follows:

- backend-focused members verify API correctness, database constraints, and order/cart logic;
- frontend-focused members verify interface behaviour, confirmation flows, and multilingual rendering;
- all members participate in integration and acceptance testing across major business scenarios.

### 6.1.2 Types of Tests Applied

The project uses several levels of testing:

1. **Debugging and troubleshooting**
   - browser developer tools for Vue warnings, network traces, and console logs;
   - backend logs and FastAPI exception traces;
   - agent action-suggestion logs for conversation-driven cart actions.

2. **Unit/API tests**
   - the `agentserver/tests/test_api.py` suite validates key microservice behaviours;
   - current automated tests cover chat responses against a local database and the two-stage cart add confirmation flow.

3. **Integration tests**
   - integration between frontend, backend, agentserver, and database is validated through end-to-end manual scenarios;
   - special attention is given to the chain from natural-language input to confirmation dialog to actual cart mutation.

4. **Acceptance tests**
   - requirement-based acceptance testing is conducted against customer flow, vendor flow, multilingual display, SKU handling, and order-state transitions.

### 6.1.3 Test Case Design

Test cases are based on the major requirements and on boundary conditions. They are designed to avoid repetitive testing by choosing representative scenarios that stress the most non-trivial parts of the system.

Representative examples include:

- registering and logging in with valid and invalid credentials;
- adding a valid SKU and an invalid SKU to the cart;
- updating quantity within stock and beyond stock;
- purchasing different SKU variants of the same book;
- cancelling and confirming orders across legal and illegal transitions;
- asking the agent for recommendations, clarification, and current-user cart operations;
- ensuring that canceling an agent confirmation dialog leaves the database unchanged.

### 6.1.4 Validation and Error Checking

Major functions are guarded through several layers of validation:

- Pydantic schemas validate request structures;
- business logic validates availability and stock before cart writes and order creation;
- confirmation tokens validate two-stage cart mutations in the agent service;
- conversation ownership checks prevent session crossover;
- structured status codes are used to distinguish validation, authorization, and business-rule failures.

### 6.1.5 Sample Data and Robustness

The system uses seeded sample data to support robust testing. The dataset includes:

- multiple books with bilingual metadata;
- configurable books with multiple SKUs;
- real cover images and local image caches;
- predefined user and admin accounts;
- order and status-event testability through repeatable seed scripts.

This dataset supports testing of search, pagination, SKU selection, inventory validation, order timelines, admin operations, and agent recommendations without relying on manually handcrafted one-off records.

## 6.2 Security

### 6.2.1 External Security Overview

The system incorporates several security controls from the perspective of external behaviour:

- authenticated operations require a valid token;
- cart mutation endpoints in the agent layer require CSRF validation;
- text input is checked for obviously unsafe content;
- cart writes are not executed directly from chat but must pass confirmation;
- the agent is restricted to a small white-listed set of database capabilities;
- conversation identifiers are bound to the current user or current anonymous client.

### 6.2.2 Mitigated Vulnerabilities

The main mitigated risks are:

- unauthorized access to user-only functionality;
- cross-user data exposure through reused conversations;
- XSS-style payload submission through chat text;
- CSRF against cart modification requests;
- accidental or malicious cart mutation without explicit confirmation;
- abuse of the agent layer to reach admin or payment behaviour.

### 6.2.3 Security Testing

Relevant tests and checks include:

- verifying 401/403 responses when cart endpoints are accessed without valid credentials;
- checking rejection of invalid confirmation tokens;
- checking rejection of conversation reuse across users;
- manual injection of suspicious script-like content into chat requests;
- observing rate-limited behaviour on repeated requests;
- confirming that cancelling dialogs does not mutate the cart.

While formal load or DoS testing is not the main focus of the coursework system, the current design already includes rate limiting and logging mechanisms that provide a basis for future stress testing.

## 6.3 Reflection on User Experience

The project attempts to support a diverse user base through multilingual UI, readable confirmation dialogs, and increasingly guided natural-language interaction.

### 6.3.1 Different Age Groups and Experience Levels

- users familiar with e-commerce can use conventional product, cart, and checkout pages efficiently;
- users less familiar with structured interfaces can rely on the intelligent agent for conversational guidance;
- explicit confirmation dialogs reduce accidental mistakes for less experienced users.

### 6.3.2 Cultural and Language Diversity

- the interface supports simplified Chinese, traditional Chinese, English, and Japanese;
- product fields are stored bilingually, reducing loss of meaning across interface language switches;
- the assistant drawer includes guidance content so that users understand how to phrase queries more effectively.

### 6.3.3 Accessibility Considerations

The system includes several basic accessibility-oriented choices:

- enlarged dialog text for cart confirmations;
- explicit confirm/cancel buttons rather than implicit gestures;
- text-plus-colour signalling for stock or availability problems;
- mobile-friendly layout behaviour for dialogs and drawers;
- avoidance of automatic destructive behaviour without manual user confirmation.

### 6.3.4 UX Reflection from Testing

Testing and debugging revealed several important lessons:

- short-lived toast messages are inadequate for critical cart confirmations;
- if the LLM performs confirmation inside the conversation, users may believe the action executed when it has not;
- shopping-cart targeting is difficult when book title and edition are not clearly stated;
- user guidance significantly improves the quality of natural-language inputs.

These observations directly motivated the current design of centered confirmation dialogs, collapsible usage guidance, and current-user cart restriction.

## 6.4 Other Qualities

### 6.4.1 Maintainability

Maintainability is a significant concern because the project contains multiple interacting subsystems. The required level is moderate to high maintainability. This is supported through:

- separation of frontend, backend, and agentserver;
- layered backend structure using routers, schemas, repositories, and services;
- requirement traceability through identifiers in code and documentation;
- documentation designed as a report-ready technical reference.

### 6.4.2 Extensibility

The system is expected to remain extensible enough to support future migration and feature growth. The current design supports this through:

- SKU-based product modelling;
- the separation of current state and event history;
- independent agent microservice deployment;
- a skill-oriented design within the agent layer.

### 6.4.3 Explainability

Explainability is especially important in a coursework system. The architecture, database model, state machines, and agent boundaries are all designed so that they can be clearly explained in documentation and oral presentation.

---

# Chapter 7 Conclusion and Further Work

## 7.1 Conclusion

This project delivers a local-run online bookstore system with a complete and explainable structure. It supports customer-side and vendor-side business processes, SKU-based product modelling, multilingual presentation, order state tracking, and intelligent-agent-assisted conversation and cart operations. The system goes beyond a simple demonstration website by incorporating a meaningful architecture, a structured data model, dynamic process modelling, security controls, and quality considerations.

From a software engineering perspective, the project demonstrates how a relatively compact coursework system can still embody important engineering ideas such as service separation, repository restriction, state-machine modelling, requirement-based verification, and human-in-the-loop confirmation for AI-assisted operations.

## 7.2 Further Work

Several directions for future enhancement are identified:

1. **Business features**
   - add payment, coupon, logistics, and after-sales workflows;
   - strengthen reporting and analytics dashboards;
   - expand review and recommendation functions.

2. **Database and performance**
   - migrate from SQLite to PostgreSQL;
   - introduce Alembic-based schema migration;
   - improve indexing and text-search support;
   - add summarized reporting tables or materialized views.

3. **Agent capabilities**
   - strengthen structured tool-calling behaviour;
   - improve disambiguation of cart targets and SKU variants;
   - add richer recommendation features and possibly order-related support under safe constraints.

4. **Quality engineering**
   - broaden automated test coverage;
   - add frontend component tests and end-to-end browser tests;
   - conduct stronger stress and security testing;
   - improve accessibility validation with more systematic user studies.

## 7.3 Final Remarks

The project provides a useful foundation for both demonstration and further research-oriented improvement. Its current implementation already satisfies the main goal of combining an online bookstore domain with a modern intelligent-agent interaction layer under explicit safety constraints. With additional engineering effort, the same design can be extended toward a more production-like and analytically richer system.
