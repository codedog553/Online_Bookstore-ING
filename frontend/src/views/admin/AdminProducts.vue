<template>
  <div>
    <h2>{{ t('admin.productsTitle') }}</h2>

    <el-card class="mb16">
      <template #header>
        <div style="display:flex;gap:8px;align-items:center;justify-content:space-between">
          <span>{{ t('admin.search') }}</span>
          <div style="display:flex;gap:8px;align-items:center">
            <el-input v-model="q" :placeholder="t('admin.keyword')" style="width:260px" @keyup.enter="load" />
            <el-checkbox v-model="searchById">{{ t('admin.searchById') }}</el-checkbox>
            <el-button @click="load">{{ t('admin.search') }}</el-button>
          </div>
        </div>
      </template>
    </el-card>

    <el-card class="mb16">
      <template #header>{{ t('admin.newProduct') }}</template>
      <el-form :model="form" label-width="110px" @keyup.enter="create">
        <el-form-item :label="t('admin.title')"><el-input v-model="form.title" /></el-form-item>
        <el-form-item :label="t('admin.titleEn')"><el-input v-model="form.title_en" /></el-form-item>
        <el-form-item :label="t('product.author')"><el-input v-model="form.author" /></el-form-item>
        <el-form-item :label="t('admin.authorEn')"><el-input v-model="form.author_en" /></el-form-item>
        <el-form-item :label="t('product.publisher')"><el-input v-model="form.publisher" /></el-form-item>
        <el-form-item :label="t('product.publisherEn')"><el-input v-model="form.publisher_en" /></el-form-item>
        <el-form-item :label="t('admin.basePrice')"><el-input v-model.number="form.base_price" type="number" /></el-form-item>
        <el-form-item :label="t('admin.description')"><el-input type="textarea" v-model="form.description" /></el-form-item>
        <el-form-item :label="t('admin.descriptionEn')"><el-input type="textarea" v-model="form.description_en" /></el-form-item>
        <el-form-item :label="t('admin.optionsConfig')">
          <div class="optionBuilder">
            <div v-if="!createOptionItems.length" class="helperText">{{ t('admin.noProductOptions') }}</div>
            <div v-for="(option, optionIndex) in createOptionItems" :key="`create-${optionIndex}`" class="optionCard">
              <div class="optionHeader">
                <el-input v-model="option.key" :placeholder="t('admin.optionNamePlaceholder')" />
                <el-button text type="danger" @click="removeCreateOption(optionIndex)">{{ t('admin.delete') }}</el-button>
              </div>
              <div v-for="(value, valueIndex) in option.values" :key="`create-${optionIndex}-${valueIndex}`" class="optionValueRow">
                <el-input v-model="value.zh" :placeholder="t('admin.optionValuePlaceholder')" />
                <el-input v-model="value.en" :placeholder="t('admin.optionValueEnPlaceholder')" />
                <el-button text type="danger" @click="removeCreateOptionValue(optionIndex, valueIndex)">{{ t('admin.delete') }}</el-button>
              </div>
              <el-button link type="primary" @click="addCreateOptionValue(optionIndex)">{{ t('admin.addOptionValue') }}</el-button>
            </div>
            <div class="optionActions">
              <el-button @click="addCreateOption">{{ t('admin.addOption') }}</el-button>
            </div>
            <div class="helperText">{{ t('admin.optionsBuilderHint') }}</div>
          </div>
        </el-form-item>
        <el-form-item :label="t('admin.isActive')"><el-switch v-model="form.is_active" /></el-form-item>
        <el-form-item>
          <div style="color:#888;line-height:1.4">
            {{ t('admin.skuPhotos') }}：{{ t('admin.selectSkuTip') }}
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="create">{{ t('admin.save') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="list" v-loading="loading" style="width:100%">
      <el-table-column prop="id" :label="t('admin.id')" width="80" />
      <el-table-column prop="title" :label="t('admin.title')" />
      <el-table-column prop="author" :label="t('product.author')" width="160" />
      <el-table-column :label="t('product.price')" width="140">
        <template #default="{ row }">￥{{ (row.min_price ?? row.base_price).toFixed ? (row.min_price ?? row.base_price).toFixed(2) : row.min_price ?? row.base_price }}</template>
      </el-table-column>
      <el-table-column :label="t('admin.isActive')" width="120">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" @change="() => toggleActive(row)" />
        </template>
      </el-table-column>
      <el-table-column :label="t('admin.operations')" width="260">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">{{ t('admin.editProduct') }}</el-button>
          <el-button size="small" @click="openSkuDialog(row)">{{ t('admin.manageSku') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editVisible" width="720px" :title="t('admin.editProduct')">
      <el-form v-if="editForm" :model="editForm" label-width="120px">
        <el-form-item :label="t('admin.id')"><el-input :model-value="String(editForm.id)" disabled /></el-form-item>
        <el-form-item :label="t('admin.title')"><el-input v-model="editForm.title" /></el-form-item>
        <el-form-item :label="t('admin.titleEn')"><el-input v-model="editForm.title_en" /></el-form-item>
        <el-form-item :label="t('product.author')"><el-input v-model="editForm.author" /></el-form-item>
        <el-form-item :label="t('admin.authorEn')"><el-input v-model="editForm.author_en" /></el-form-item>
        <el-form-item :label="t('product.publisher')"><el-input v-model="editForm.publisher" /></el-form-item>
        <el-form-item :label="t('product.publisherEn')"><el-input v-model="editForm.publisher_en" /></el-form-item>
        <el-form-item :label="t('admin.basePrice')"><el-input v-model.number="editForm.base_price" type="number" /></el-form-item>
        <el-form-item :label="t('admin.description')"><el-input type="textarea" v-model="editForm.description" /></el-form-item>
        <el-form-item :label="t('admin.descriptionEn')"><el-input type="textarea" v-model="editForm.description_en" /></el-form-item>
        <el-form-item :label="t('admin.optionsConfig')">
          <div class="optionBuilder">
            <div v-if="!editOptionItems.length" class="helperText">{{ t('admin.noProductOptions') }}</div>
            <div v-for="(option, optionIndex) in editOptionItems" :key="`edit-${optionIndex}`" class="optionCard">
              <div class="optionHeader">
                <el-input v-model="option.key" :placeholder="t('admin.optionNamePlaceholder')" />
                <el-button text type="danger" @click="removeEditOption(optionIndex)">{{ t('admin.delete') }}</el-button>
              </div>
              <div v-for="(value, valueIndex) in option.values" :key="`edit-${optionIndex}-${valueIndex}`" class="optionValueRow">
                <el-input v-model="value.zh" :placeholder="t('admin.optionValuePlaceholder')" />
                <el-input v-model="value.en" :placeholder="t('admin.optionValueEnPlaceholder')" />
                <el-button text type="danger" @click="removeEditOptionValue(optionIndex, valueIndex)">{{ t('admin.delete') }}</el-button>
              </div>
              <el-button link type="primary" @click="addEditOptionValue(optionIndex)">{{ t('admin.addOptionValue') }}</el-button>
            </div>
            <div class="optionActions">
              <el-button @click="addEditOption">{{ t('admin.addOption') }}</el-button>
            </div>
            <div class="helperText">{{ t('admin.optionsBuilderHint') }}</div>
          </div>
        </el-form-item>
        <el-form-item :label="t('admin.isActive')"><el-switch v-model="editForm.is_active" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible=false">{{ t('auth.confirm') }}</el-button>
        <el-button type="primary" :loading="savingEdit" @click="saveEdit">{{ t('admin.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="skuDialogVisible" width="900px" :title="`${t('admin.manageSku')} - #${currentProduct?.id} ${currentProduct?.title}`">
      <div v-if="currentProduct">
        <el-table :data="skus" size="small" style="width:100%" class="mb16" @row-click="(row:any) => (selectedSku = row)">
          <el-table-column :label="t('cart.config')">
            <template #default="{ row }">{{ parseOption(row.option_values) }}</template>
          </el-table-column>
          <el-table-column :label="t('admin.priceAdjustment')" width="120">
            <template #default="{ row }">
              <el-input v-model.number="row.price_adjustment" type="number" @change="() => saveSku(row)" />
            </template>
          </el-table-column>
          <el-table-column :label="t('admin.stockQuantity')" width="120">
            <template #default="{ row }">
              <el-input v-model.number="row.stock_quantity" type="number" @change="() => saveSku(row)" />
            </template>
          </el-table-column>
          <el-table-column :label="t('admin.available')" width="120">
            <template #default="{ row }">
              <el-switch v-model="row.is_available" @change="() => saveSku(row)" />
            </template>
          </el-table-column>
          <el-table-column :label="t('admin.operations')" width="120">
            <template #default="{ row }">
              <el-button type="danger" size="small" @click="delSku(row)">{{ t('admin.delete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-card class="mb16">
          <template #header>
            <div style="display:flex;align-items:center;justify-content:space-between">
              <span>{{ t('admin.skuPhotos') }}</span>
              <span style="color:#888" v-if="selectedSku">#{{ selectedSku.id }} ({{ parseOption(selectedSku.option_values) }})</span>
            </div>
          </template>

          <div v-if="!selectedSku" style="color:#888">{{ t('admin.selectSkuTip') }}</div>

          <div v-else>
            <el-upload
              multiple
              :show-file-list="false"
              :http-request="uploadSkuPhotos"
              :disabled="uploadingPhotos"
            >
              <el-button type="primary" :loading="uploadingPhotos">{{ t('admin.uploadSkuPhotos') }}</el-button>
            </el-upload>

            <div class="photoGrid" v-if="parsePhotos(selectedSku.photos).length">
              <div v-for="p in parsePhotos(selectedSku.photos)" :key="p" class="photoItem">
                <el-image :src="p" style="width:96px;height:96px" fit="cover" />
                <div style="margin-top:6px;display:flex;justify-content:center">
                  <el-button size="small" type="danger" @click="deletePhoto(p)">{{ t('admin.delete') }}</el-button>
                </div>
              </div>
            </div>
            <div v-else style="color:#888;margin-top:10px">{{ t('admin.noPhotos') }}</div>
          </div>
        </el-card>

        <h4>{{ t('admin.newSku') }}</h4>
        <el-form :model="newSku" label-width="120px">
          <el-form-item :label="t('admin.optionSelection')">
            <div class="skuOptionBuilder">
              <template v-if="currentProductOptionItems.length">
                <div v-for="option in currentProductOptionItems" :key="option.key" class="skuOptionRow">
                  <span class="skuOptionLabel">{{ option.key }}</span>
                  <el-select v-model="newSkuSelections[option.key]" :placeholder="t('product.select')" style="width:100%">
                    <el-option
                      v-for="value in option.values"
                      :key="`${option.key}-${value.zh}`"
                      :label="formatOptionChoice(value)"
                      :value="value.zh"
                    />
                  </el-select>
                </div>
              </template>
              <div v-else class="helperText">{{ t('admin.simpleSkuHint') }}</div>
            </div>
          </el-form-item>
          <el-form-item :label="t('admin.priceAdjustment')">
            <el-input v-model.number="newSku.price_adjustment" type="number" />
          </el-form-item>
          <el-form-item :label="t('admin.stockQuantity')">
            <el-input v-model.number="newSku.stock_quantity" type="number" />
          </el-form-item>
          <el-form-item :label="t('admin.available')">
            <el-switch v-model="newSku.is_available" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="savingSku" @click="createSku">{{ t('admin.addSku') }}</el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import api from '../../api/http'
import { extractErrorMessage } from '../../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'

// =========================
// Requirements Traceability
// =========================
// A14: vendor/admin 可浏览/搜索商品目录。
// A15: 管理端显式勾选“按 ID 查找”后，仅按商品 ID 搜索；未勾选时按 title/title_en 搜索。
// A16: 可新增商品（包含中英双语字段）；图片按 SKU 维度本地上传、可多张。
// A17: 可编辑商品详情。
// A18: 可上架/下架（is_active）。
// B1: 管理端允许对 SKU 上传/删除多张图片。
// D1/D4: 商品 options 定义可配置商品；不同配置作为不同 SKU 独立维护库存/可售。
// W2: 新建/编辑商品时强制填写中英双语信息（前端校验 + 后端 schema 校验）。

interface Product {
  id:number
  title:string
  title_en?: string | null
  author?:string | null
  author_en?: string | null
  publisher?: string | null
  publisher_en?: string | null
  base_price:number
  min_price?:number|null
  is_active:boolean
  description?:string|null
  description_en?: string | null
  options?:string|null
}
interface SKU { id:number; product_id:number; option_values:string; price_adjustment:number; stock_quantity:number; is_available:boolean; photos?: string | null }
interface OptionValueDraft { zh:string; en:string }
interface ProductOptionDraft { key:string; values: OptionValueDraft[] }

const { t } = useI18n()

const q = ref('')
const searchById = ref(false)

const list = ref<Product[]>([])
const loading = ref(false)
const saving = ref(false)
const form = ref({
  title:'',
  title_en:'',
  author:'',
  author_en:'',
  publisher:'',
  publisher_en:'',
  base_price: 0,
  is_active: true,
  description:'',
  description_en:'',
  options:''
})
const createOptionItems = ref<ProductOptionDraft[]>([])
const createOptionExtra = ref<Record<string, any>>({})

const editVisible = ref(false)
const savingEdit = ref(false)
const editForm = ref<any | null>(null)
const editOptionItems = ref<ProductOptionDraft[]>([])
const editOptionExtra = ref<Record<string, any>>({})

const skuDialogVisible = ref(false)
const currentProduct = ref<Product | null>(null)
const skus = ref<SKU[]>([])
const selectedSku = ref<SKU | null>(null)
const savingSku = ref(false)
const newSku = ref({ option_values: '{}', price_adjustment: 0, stock_quantity: 0, is_available: true })
const newSkuSelections = ref<Record<string, string>>({})

const uploadingPhotos = ref(false)
const currentProductOptionItems = computed(() => parseManagedOptions(currentProduct.value?.options).items)

function parsePhotos(s: any): string[] {
  const v = (s ?? '').toString().trim()
  if (!v) return []
  try {
    const arr = JSON.parse(v)
    return Array.isArray(arr) ? arr.map((x) => String(x)) : []
  } catch {
    return []
  }
}

function createEmptyOptionValue(): OptionValueDraft {
  return { zh: '', en: '' }
}

function createEmptyOption(): ProductOptionDraft {
  return { key: '', values: [createEmptyOptionValue()] }
}

function safeParseObject(s: any): Record<string, any> {
  const raw = (s ?? '').toString().trim()
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, any> : {}
  } catch {
    return {}
  }
}

function parseManagedOptions(s: any): { items: ProductOptionDraft[]; extra: Record<string, any> } {
  const parsed = safeParseObject(s)
  const optionValueI18n = parsed.optionValueI18n && typeof parsed.optionValueI18n === 'object' && !Array.isArray(parsed.optionValueI18n)
    ? parsed.optionValueI18n as Record<string, Record<string, string>>
    : {}
  const items: ProductOptionDraft[] = []
  const extra: Record<string, any> = {}

  Object.entries(parsed).forEach(([key, value]) => {
    if (key === 'optionValueI18n') return
    if (Array.isArray(value)) {
      items.push({
        key,
        values: value.length
          ? value.map((item) => {
              const zh = String(item)
              return { zh, en: optionValueI18n?.[key]?.[zh] || '' }
            })
          : [createEmptyOptionValue()],
      })
      return
    }
    extra[key] = value
  })

  return { items, extra }
}

function serializeManagedOptions(items: ProductOptionDraft[], extra: Record<string, any> = {}): string {
  const payload: Record<string, any> = { ...extra }
  const optionValueI18n: Record<string, Record<string, string>> = {}

  items.forEach((item) => {
    const key = item.key.trim()
    const values = item.values
      .map((value) => ({ zh: value.zh.trim(), en: value.en.trim() }))
      .filter((value) => value.zh)

    if (!key || !values.length) return

    payload[key] = values.map((value) => value.zh)

    const translatedValues = values.filter((value) => value.en)
    if (translatedValues.length) {
      optionValueI18n[key] = {}
      translatedValues.forEach((value) => {
        optionValueI18n[key][value.zh] = value.en
      })
    }
  })

  if (Object.keys(optionValueI18n).length) payload.optionValueI18n = optionValueI18n
  return Object.keys(payload).length ? JSON.stringify(payload) : ''
}

function syncCreateOptions() {
  form.value.options = serializeManagedOptions(createOptionItems.value, createOptionExtra.value)
}

function syncEditOptions() {
  if (!editForm.value) return
  editForm.value.options = serializeManagedOptions(editOptionItems.value, editOptionExtra.value)
}

function addCreateOption() {
  createOptionItems.value.push(createEmptyOption())
}

function removeCreateOption(index: number) {
  createOptionItems.value.splice(index, 1)
}

function addCreateOptionValue(index: number) {
  createOptionItems.value[index]?.values.push(createEmptyOptionValue())
}

function removeCreateOptionValue(optionIndex: number, valueIndex: number) {
  const values = createOptionItems.value[optionIndex]?.values
  if (!values) return
  values.splice(valueIndex, 1)
  if (!values.length) values.push(createEmptyOptionValue())
}

function addEditOption() {
  editOptionItems.value.push(createEmptyOption())
}

function removeEditOption(index: number) {
  editOptionItems.value.splice(index, 1)
}

function addEditOptionValue(index: number) {
  editOptionItems.value[index]?.values.push(createEmptyOptionValue())
}

function removeEditOptionValue(optionIndex: number, valueIndex: number) {
  const values = editOptionItems.value[optionIndex]?.values
  if (!values) return
  values.splice(valueIndex, 1)
  if (!values.length) values.push(createEmptyOptionValue())
}

function resetNewSkuSelections() {
  const next: Record<string, string> = {}
  currentProductOptionItems.value.forEach((option) => {
    next[option.key] = ''
  })
  newSkuSelections.value = next
}

function buildNewSkuOptionValues(): string {
  const payload: Record<string, string> = {}
  for (const option of currentProductOptionItems.value) {
    const key = option.key.trim()
    if (!key) continue
    const value = (newSkuSelections.value[key] || '').trim()
    if (!value) throw new Error('missing-option')
    payload[key] = value
  }
  return JSON.stringify(payload)
}

function formatOptionChoice(value: OptionValueDraft): string {
  return value.en ? `${value.zh} / ${value.en}` : value.zh
}

watch(createOptionItems, syncCreateOptions, { deep: true })
watch(editOptionItems, syncEditOptions, { deep: true })

async function load(){
  loading.value = true
  try {
    const params: Record<string, string | boolean> = {}
    if (q.value) params.q = q.value
    if (searchById.value) params.search_by_id = true
    const { data } = await api.get('/api/admin/products', { params })
    list.value = data
  } finally { loading.value = false }
}

async function create(){
  syncCreateOptions()
  if (!form.value.title || !form.value.base_price || !form.value.title_en) {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }

  // W2: 新建商品要求中英双语字段
  if (!form.value.author || !form.value.author_en || !form.value.publisher || !form.value.publisher_en || !form.value.description || !form.value.description_en) {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }

  if (!safeJsonOrEmpty(form.value.options)) {
    ElMessage.warning(t('msg.invalidJson'))
    return
  }
  saving.value = true
  try {
    await api.post('/api/admin/products', form.value)
    form.value = { title:'', title_en:'', author:'', author_en:'', publisher:'', publisher_en:'', base_price: 0, is_active: true, description:'', description_en:'', options:'' }
    createOptionItems.value = []
    createOptionExtra.value = {}
    await load()
  } catch(e:any){
    ElMessage.error(extractErrorMessage(e, t('msg.saveFailed')))
  } finally { saving.value = false }
}

async function toggleActive(row: Product){
  try {
    await api.put(`/api/admin/products/${row.id}`, { is_active: row.is_active })
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('msg.updateFailed')))
  }
}

function parseOption(s: string){
  try { const obj = JSON.parse(s); return Object.entries(obj).map(([k,v])=>`${k}:${v}`).join(', ') } catch { return s }
}

async function openSkuDialog(p: Product){
  currentProduct.value = p
  resetNewSkuSelections()
  newSku.value = { option_values: '{}', price_adjustment: 0, stock_quantity: 0, is_available: true }
  skuDialogVisible.value = true
  await fetchSkus()
  selectedSku.value = skus.value?.[0] || null
}

async function fetchSkus(){
  if (!currentProduct.value) return
  try {
    const { data } = await api.get(`/api/admin/products/${currentProduct.value.id}/skus`)
    skus.value = data
    if (selectedSku.value) {
      const found = skus.value.find((x) => x.id === selectedSku.value?.id)
      selectedSku.value = found || skus.value?.[0] || null
    }
  } catch(e:any){
    ElMessage.error(extractErrorMessage(e, t('msg.loadFailed')))
  }
}

async function saveSku(row: SKU){
  try {
    await api.put(`/api/admin/skus/${row.id}`, {
      option_values: row.option_values,
      price_adjustment: row.price_adjustment,
      stock_quantity: row.stock_quantity,
      is_available: row.is_available,
    })
  } catch(e:any){
    ElMessage.error(extractErrorMessage(e, t('msg.saveFailed')))
    await fetchSkus()
  }
}

async function delSku(row: SKU){
  try {
    await api.delete(`/api/admin/skus/${row.id}`)
    await fetchSkus()
  } catch(e:any){
    ElMessage.error(extractErrorMessage(e, t('msg.deleteFailed')))
  }
}

async function uploadSkuPhotos(file: any){
  // ElementPlus http-request hook
  if (!selectedSku.value) return
  uploadingPhotos.value = true
  try {
    const form = new FormData()
    // 后端参数名为 files: List[UploadFile]
    form.append('files', file.file)
    await api.post(`/api/admin/skus/${selectedSku.value.id}/photos`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(t('admin.uploadSuccess'))
    await fetchSkus()
  } catch(e:any) {
    ElMessage.error(extractErrorMessage(e, t('admin.uploadFailed')))
  } finally {
    uploadingPhotos.value = false
  }
}

async function deletePhoto(path: string){
  if (!selectedSku.value) return
  try {
    await api.delete(`/api/admin/skus/${selectedSku.value.id}/photos`, { params: { path } })
    ElMessage.success(t('admin.deleteSuccess'))
    await fetchSkus()
  } catch(e:any){
    ElMessage.error(extractErrorMessage(e, t('msg.deleteFailed')))
  }
}

async function createSku(){
  if (!currentProduct.value) return
  try {
    newSku.value.option_values = buildNewSkuOptionValues()
  } catch {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }
  savingSku.value = true
  try {
    await api.post(`/api/admin/products/${currentProduct.value.id}/skus`, newSku.value)
    newSku.value = { option_values: '{}', price_adjustment: 0, stock_quantity: 0, is_available: true }
    resetNewSkuSelections()
    await fetchSkus()
  } catch(e:any){
    ElMessage.error(extractErrorMessage(e, t('msg.saveFailed')))
  } finally {
    savingSku.value = false
  }
}

function safeJsonOrEmpty(s: any): boolean {
  const v = (s ?? '').toString().trim()
  if (!v) return true
  try { JSON.parse(v); return true } catch { return false }
}

function openEdit(p: Product) {
  editForm.value = JSON.parse(JSON.stringify(p))
  const parsed = parseManagedOptions(editForm.value.options)
  editOptionItems.value = parsed.items
  editOptionExtra.value = parsed.extra
  syncEditOptions()
  editVisible.value = true
}

async function saveEdit() {
  if (!editForm.value) return
  syncEditOptions()
  if (!editForm.value.title || !editForm.value.base_price || !editForm.value.title_en) {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }

  if (!editForm.value.author || !editForm.value.author_en || !editForm.value.publisher || !editForm.value.publisher_en || !editForm.value.description || !editForm.value.description_en) {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }
  if (!safeJsonOrEmpty(editForm.value.options)) {
    ElMessage.warning(t('msg.invalidJson'))
    return
  }
  savingEdit.value = true
  try {
    await api.put(`/api/admin/products/${editForm.value.id}`, {
      title: editForm.value.title,
      title_en: editForm.value.title_en,
      author: editForm.value.author,
      author_en: editForm.value.author_en,
      publisher: editForm.value.publisher,
      publisher_en: editForm.value.publisher_en,
      base_price: editForm.value.base_price,
      description: editForm.value.description,
      description_en: editForm.value.description_en,
      options: editForm.value.options,
      is_active: editForm.value.is_active,
    })
    editVisible.value = false
    await load()
    ElMessage.success(t('admin.updated'))
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('msg.updateFailed')))
  } finally {
    savingEdit.value = false
  }
}

onMounted(load)
</script>
<style scoped>
.mb16{ margin-bottom:16px }
.photoGrid{ margin-top:12px; display:flex; flex-wrap:wrap; gap:12px }
.photoItem{ width:110px; padding:8px; background:#ffffff; border:1px solid var(--el-border-color-light); border-radius:10px; box-shadow: 0 6px 14px rgba(24,52,110,0.06); }
.optionBuilder{ width:100% }
.optionCard{ padding:14px; margin-bottom:12px; background:#fafbfd; border:1px solid var(--el-border-color-light); border-radius:12px }
.optionHeader{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:10px; align-items:center; margin-bottom:10px }
.optionValueRow{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr) auto; gap:10px; align-items:center; margin-bottom:8px }
.optionActions{ margin-top:8px }
.helperText{ color:#7a8191; line-height:1.5 }
.skuOptionBuilder{ width:100% }
.skuOptionRow{ display:grid; grid-template-columns:120px minmax(0,1fr); gap:12px; align-items:center; margin-bottom:10px }
.skuOptionLabel{ color:var(--el-text-color-regular); font-weight:600 }
@media (max-width: 768px){
  .optionHeader,.optionValueRow,.skuOptionRow{ grid-template-columns:1fr }
}
</style>
