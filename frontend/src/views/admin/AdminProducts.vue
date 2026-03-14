<template>
  <div>
    <h2>{{ t('admin.productsTitle') }}</h2>

    <el-card class="mb16">
      <template #header>
        <div style="display:flex;gap:8px;align-items:center;justify-content:space-between">
          <span>{{ t('admin.search') }}</span>
          <div style="display:flex;gap:8px;align-items:center">
            <el-input v-model="q" :placeholder="t('admin.keyword')" style="width:260px" @keyup.enter="load" />
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
        <el-form-item :label="t('admin.basePrice')"><el-input v-model.number="form.base_price" type="number" /></el-form-item>
        <el-form-item :label="t('admin.description')"><el-input type="textarea" v-model="form.description" /></el-form-item>
        <el-form-item :label="t('admin.descriptionEn')"><el-input type="textarea" v-model="form.description_en" /></el-form-item>
        <el-form-item :label="t('admin.imagesJson')">
          <el-input type="textarea" v-model="form.images" placeholder='例如 ["https://...","https://..."]' />
        </el-form-item>
        <el-form-item :label="t('admin.optionsJson')">
          <el-input type="textarea" v-model="form.options" placeholder='例如 {"版本":["平装","精装"], "optionImages": {"版本": {"平装":"https://..."}}}' />
        </el-form-item>
        <el-form-item :label="t('admin.isActive')"><el-switch v-model="form.is_active" /></el-form-item>
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
        <el-form-item :label="t('admin.basePrice')"><el-input v-model.number="editForm.base_price" type="number" /></el-form-item>
        <el-form-item :label="t('admin.description')"><el-input type="textarea" v-model="editForm.description" /></el-form-item>
        <el-form-item :label="t('admin.descriptionEn')"><el-input type="textarea" v-model="editForm.description_en" /></el-form-item>
        <el-form-item :label="t('admin.imagesJson')">
          <el-input type="textarea" v-model="editForm.images" />
          <div style="margin-top:6px;display:flex;gap:8px;align-items:center" v-if="firstImageUrl(editForm.images)">
            <el-image :src="firstImageUrl(editForm.images)" style="width:80px;height:80px" fit="cover" />
          </div>
        </el-form-item>
        <el-form-item :label="t('admin.optionsJson')"><el-input type="textarea" v-model="editForm.options" /></el-form-item>
        <el-form-item :label="t('admin.isActive')"><el-switch v-model="editForm.is_active" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible=false">{{ t('auth.confirm') }}</el-button>
        <el-button type="primary" :loading="savingEdit" @click="saveEdit">{{ t('admin.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="skuDialogVisible" width="860px" :title="`${t('admin.manageSku')} - #${currentProduct?.id} ${currentProduct?.title}`">
      <div v-if="currentProduct">
        <el-table :data="skus" size="small" style="width:100%" class="mb16">
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

        <h4>{{ t('admin.newSku') }}</h4>
        <el-form :model="newSku" label-width="120px">
          <el-form-item :label="t('admin.optionValuesJson')">
            <el-input type="textarea" v-model="newSku.option_values" placeholder='例如 {"version":"标准"}' />
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
import { ref, onMounted } from 'vue'
import api from '../../api/http'
import { extractErrorMessage } from '../../api/error'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'

interface Product {
  id:number
  title:string
  title_en?: string | null
  author?:string | null
  author_en?: string | null
  base_price:number
  min_price?:number|null
  is_active:boolean
  description?:string|null
  description_en?: string | null
  images?:string|null
  options?:string|null
}
interface SKU { id:number; product_id:number; option_values:string; price_adjustment:number; stock_quantity:number; is_available:boolean }

const { t } = useI18n()

const q = ref('')

const list = ref<Product[]>([])
const loading = ref(false)
const saving = ref(false)
const form = ref({
  title:'',
  title_en:'',
  author:'',
  author_en:'',
  base_price: 0,
  is_active: true,
  description:'',
  description_en:'',
  images:'',
  options:''
})

const editVisible = ref(false)
const savingEdit = ref(false)
const editForm = ref<any | null>(null)

const skuDialogVisible = ref(false)
const currentProduct = ref<Product | null>(null)
const skus = ref<SKU[]>([])
const savingSku = ref(false)
const newSku = ref({ option_values: '{}', price_adjustment: 0, stock_quantity: 0, is_available: true })

async function load(){
  loading.value = true
  try {
    const { data } = await api.get('/api/admin/products', { params: q.value ? { q: q.value } : {} })
    list.value = data
  } finally { loading.value = false }
}

async function create(){
  if (!form.value.title || !form.value.base_price) {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }

  if (!safeJsonOrEmpty(form.value.images) || !safeJsonOrEmpty(form.value.options)) {
    ElMessage.warning(t('msg.invalidJson'))
    return
  }
  saving.value = true
  try {
    await api.post('/api/admin/products', form.value)
    form.value = { title:'', title_en:'', author:'', author_en:'', base_price: 0, is_active: true, description:'', description_en:'', images:'', options:'' }
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
  skuDialogVisible.value = true
  await fetchSkus()
}

async function fetchSkus(){
  if (!currentProduct.value) return
  try {
    const { data } = await api.get(`/api/admin/products/${currentProduct.value.id}/skus`)
    skus.value = data
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

async function createSku(){
  if (!currentProduct.value) return
  if (!safeJsonOrEmpty(newSku.value.option_values)) {
    ElMessage.warning(t('msg.invalidJson'))
    return
  }
  savingSku.value = true
  try {
    await api.post(`/api/admin/products/${currentProduct.value.id}/skus`, newSku.value)
    newSku.value = { option_values: '{}', price_adjustment: 0, stock_quantity: 0, is_available: true }
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

function firstImageUrl(s: any): string {
  const v = (s ?? '').toString().trim()
  if (!v) return ''
  try {
    const arr = JSON.parse(v)
    if (Array.isArray(arr) && arr.length) return String(arr[0] || '')
    return ''
  } catch { return '' }
}

function openEdit(p: Product) {
  editForm.value = JSON.parse(JSON.stringify(p))
  editVisible.value = true
}

async function saveEdit() {
  if (!editForm.value) return
  if (!editForm.value.title || !editForm.value.base_price) {
    ElMessage.warning(t('msg.fillRequired'))
    return
  }
  if (!safeJsonOrEmpty(editForm.value.images) || !safeJsonOrEmpty(editForm.value.options)) {
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
      base_price: editForm.value.base_price,
      description: editForm.value.description,
      description_en: editForm.value.description_en,
      images: editForm.value.images,
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
</style>
