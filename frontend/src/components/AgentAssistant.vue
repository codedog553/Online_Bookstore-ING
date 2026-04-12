<template>
  <div>
    <el-button class="agent-fab" type="primary" circle @click="visible = true">AI</el-button>
    <el-drawer v-model="visible" :title="t('agent.title')" size="420px">
      <div class="assistant-shell">
        <div class="assistant-tip">{{ t('agent.subtitle') }}</div>
        <div class="agent-guide-card">
          <div class="agent-guide-head" @click="guideExpanded = !guideExpanded">
            <div>
              <div class="agent-guide-badge">{{ t('agent.guideBadge') }}</div>
              <div class="agent-guide-title">{{ t('agent.guideTitle') }}</div>
            </div>
            <el-button text class="agent-guide-toggle">
              {{ guideExpanded ? t('agent.guideCollapse') : t('agent.guideExpand') }}
            </el-button>
          </div>
          <div v-if="guideExpanded">
            <div class="agent-guide-text">{{ t('agent.guideText') }}</div>
            <div class="agent-guide-list">
              <div class="agent-guide-item">{{ t('agent.guideExampleBrowse') }}</div>
              <div class="agent-guide-item">{{ t('agent.guideExampleAdd') }}</div>
              <div class="agent-guide-item">{{ t('agent.guideExampleUpdate') }}</div>
              <div class="agent-guide-item">{{ t('agent.guideExampleRemove') }}</div>
            </div>
          </div>
        </div>
        <div class="assistant-messages">
          <div v-for="(msg, index) in messages" :key="`${msg.created_at}-${index}`" :class="['assistant-msg', msg.role]">
            <div class="assistant-role">{{ msg.role === 'user' ? t('agent.you') : t('agent.assistant') }}</div>
            <div class="assistant-bubble">{{ msg.content }}</div>
          </div>
          <el-empty v-if="!messages.length && !loading" :description="t('agent.empty')" />
        </div>
        <el-input
          v-model="draft"
          type="textarea"
          :rows="4"
          :placeholder="t('agent.placeholder')"
          @keydown.enter.prevent="submit"
        />
        <div class="assistant-actions">
          <el-button @click="resetConversation">{{ t('agent.newChat') }}</el-button>
          <el-button type="primary" :loading="loading" @click="submit">{{ t('agent.send') }}</el-button>
        </div>
      </div>
    </el-drawer>

    <el-dialog
      v-model="confirmationVisible"
      :title="t('agent.confirmTitle')"
      :width="pendingConfirmation?.ui?.dialog_width || 'min(92vw, 560px)'"
      align-center
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="true"
    >
      <div class="agent-confirm-message" :style="{ fontSize: `${pendingConfirmation?.ui?.font_size_pt || 18}pt` }">
        {{ pendingConfirmation?.confirmation_message }}
      </div>
      <template #footer>
        <div class="agent-confirm-actions">
          <el-button size="large" @click="cancelPendingConfirmation">{{ pendingConfirmation?.ui?.cancel_label || t('common.cancel') }}</el-button>
          <el-button size="large" type="primary" @click="confirmPendingAction">{{ pendingConfirmation?.ui?.confirm_label || t('agent.confirmAction') }}</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import agentApi, { type AgentCartListResponse, type AgentChatMessage, type AgentChatResponse, type AgentConfirmationResponse } from '../api/agent'
import { extractErrorMessage } from '../api/error'

const visible = ref(false)
const loading = ref(false)
const draft = ref('')
const conversationId = ref('')
const messages = ref<AgentChatMessage[]>([])
const guideExpanded = ref(true)
const confirmationVisible = ref(false)
const pendingConfirmation = ref<AgentConfirmationResponse | null>(null)
const pendingActionPayload = ref<Record<string, any> | null>(null)
const pendingActionMethod = ref<'post' | 'put' | 'delete' | null>(null)
const pendingActionPath = ref('')
const { t } = useI18n()

async function submit() {
  const message = draft.value.trim()
  if (!message) return
  loading.value = true
  try {
    const { data } = await agentApi.post<AgentChatResponse>('/chat', {
      message,
      conversation_id: conversationId.value || undefined,
    })
    conversationId.value = data.conversation_id
    messages.value = data.history
    draft.value = ''
    console.log('[agent] action_suggestion', data.action_suggestion)
    await handleSuggestion(data, message)
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('agent.failed')))
  } finally {
    loading.value = false
  }
}

async function handleSuggestion(data: AgentChatResponse, userMessage: string) {
  const suggestion = data.action_suggestion
  console.log('[agent] handleSuggestion', suggestion)
  if (!suggestion) return

  const needsManualInfo = Boolean(suggestion.user_message) && (
    !suggestion.should_act ||
    (suggestion.action === 'add' && !suggestion.sku_id && !(suggestion.sku_requests?.length)) ||
    ((suggestion.action === 'update' || suggestion.action === 'remove') && !suggestion.item_id)
  )

  if (needsManualInfo) {
    // If backend provided candidate_items, prompt user to choose which cart item
    if (suggestion.missing_fields?.includes('item_id') && suggestion['candidate_items'] && suggestion['candidate_items'].length) {
      const candidates = suggestion['candidate_items']
      let chosen: any = null
      if (candidates.length === 1) {
        chosen = candidates[0]
      } else {
        const lines = candidates.map((it: any, idx: number) => `${idx + 1}. ${it.product_title}${it.option_summary ? ` (${it.option_summary})` : ''} x ${it.quantity || 1}`).join('\n')
        try {
          const result = await ElMessageBox.prompt(`${suggestion.user_message}\n\n${lines}\n\n请输入序号选择要操作的购物车项（例如 1）：`, t('agent.noticeTitle'), {
            confirmButtonText: t('common.confirm'),
            cancelButtonText: t('common.cancel'),
            inputPattern: /^\d+$/,
            inputErrorMessage: '请输入正确的序号',
            customClass: 'agent-centered-dialog',
          })
          const value = (result as any).value
          const idx = parseInt(String(value || ''), 10) - 1
          if (Number.isFinite(idx) && candidates[idx]) chosen = candidates[idx]
        } catch (e) {
          return
        }
      }

      if (!chosen) return

      // proceed to fetch confirmation from server depending on action
      try {
        if (suggestion.action === 'remove') {
          const { data: confirmation } = await agentApi.delete('/cart/remove', {
            data: { item_id: chosen.item_id, confirmed: false },
          })
          if (suggestion.user_message) {
            confirmation.confirmation_message = `${suggestion.user_message}\n\n${confirmation.confirmation_message}`
          }
          openConfirmationDialog(confirmation, 'delete', '/cart/remove', {
            item_id: chosen.item_id,
            confirmed: true,
            confirmation_token: confirmation.confirmation_token,
          })
          return
        }
        if (suggestion.action === 'update') {
          let quantity = suggestion.quantity
          if (typeof quantity !== 'number') {
            try {
              const result = await ElMessageBox.prompt('请输入目标数量（数字）：', t('agent.noticeTitle'), {
                confirmButtonText: t('common.confirm'),
                cancelButtonText: t('common.cancel'),
                inputPattern: /^\d+$/,
                inputErrorMessage: '请输入正确的数量',
                customClass: 'agent-centered-dialog',
              })
              const value = (result as any).value
              quantity = parseInt(String(value || ''), 10)
            } catch (e) {
              return
            }
          }
          const { data: confirmation } = await agentApi.put('/cart/update', {
            item_id: chosen.item_id,
            quantity,
            confirmed: false,
          })
          if (suggestion.user_message) {
            confirmation.confirmation_message = `${suggestion.user_message}\n\n${confirmation.confirmation_message}`
          }
          openConfirmationDialog(confirmation, 'put', '/cart/update', {
            item_id: chosen.item_id,
            quantity,
            confirmed: true,
            confirmation_token: confirmation.confirmation_token,
          })
          return
        }
      } catch (e:any) {
        ElMessage.error(extractErrorMessage(e, t('agent.failed')))
        return
      }
    }

    // fallback: show simple alert if no candidates
    // If no candidates provided by backend, try resolving from user's cart via API
    if ((suggestion.action === 'update' || suggestion.action === 'remove') && !suggestion['candidate_items']?.length && suggestion.product_title) {
      const resolved = await resolveCartItemId(suggestion.product_title, userMessage)
      if (resolved) {
        // forward to normal update/remove flow by crafting a minimal suggestion
        const minimal = Object.assign({}, suggestion, { item_id: resolved })
        // recursively handle the resolved suggestion
        await handleSuggestion({ ...data, action_suggestion: minimal } as any, userMessage)
        return
      }
    }

    await ElMessageBox.alert(suggestion.user_message, t('agent.noticeTitle'), {
      confirmButtonText: t('common.close'),
      customClass: 'agent-centered-dialog',
    })
    return
  }
    
  if (!suggestion.should_act) return

  if (suggestion.action === 'list') {
    const { data: cart } = await agentApi.get<AgentCartListResponse>('/cart')
    if (!cart.items.length) {
      await ElMessageBox.alert(t('agent.cartEmpty'), t('agent.cartTitle'), {
        confirmButtonText: t('common.close'),
        customClass: 'agent-centered-dialog',
      })
      return
    }
    const lines = cart.items.map((item) => `${item.product_title} x ${item.quantity}${item.option_summary ? ` (${item.option_summary})` : ''}`)
    await ElMessageBox.alert(lines.join('\n'), t('agent.cartTitle'), {
      confirmButtonText: t('common.close'),
      customClass: 'agent-centered-dialog',
    })
    return
  }

  if (suggestion.action === 'add' && ((suggestion.sku_requests?.length || 0) > 0 || suggestion.sku_id)) {
    const skuRequests = suggestion.sku_requests?.length
      ? suggestion.sku_requests
      : (suggestion.sku_id ? [{ sku_id: suggestion.sku_id, quantity: suggestion.quantity || 1 }] : [])

    if (!skuRequests.length) return

    const confirmationMessages: string[] = []
    const executionPayloads: Array<Record<string, any>> = []

    for (const item of skuRequests) {
      const { data: confirmation } = await agentApi.post<AgentConfirmationResponse>('/cart/add', {
        sku_id: item.sku_id,
        quantity: item.quantity,
        confirmed: false,
      })
      confirmationMessages.push(confirmation.confirmation_message)
      executionPayloads.push({
        sku_id: item.sku_id,
        quantity: item.quantity,
        confirmed: true,
        confirmation_token: confirmation.confirmation_token,
      })
      pendingConfirmation.value = confirmation
    }

    const confirmation = pendingConfirmation.value!
    if (suggestion.user_message) {
      confirmation.confirmation_message = `${suggestion.user_message}\n\n${confirmationMessages.join('\n')}`
    } else {
      confirmation.confirmation_message = confirmationMessages.join('\n')
    }
    openConfirmationDialog(confirmation, 'post', '/cart/add', {
      batch: executionPayloads,
    })
    return
  }

  if (suggestion.action === 'update' && typeof suggestion.quantity === 'number') {
    const resolvedItemId = suggestion.item_id ?? await resolveCartItemId(suggestion.product_title, userMessage)
    if (!resolvedItemId) {
      await ElMessageBox.alert(t('agent.cartTargetMissing'), t('agent.noticeTitle'), {
        confirmButtonText: t('common.close'),
        customClass: 'agent-centered-dialog',
      })
      return
    }
    const { data: confirmation } = await agentApi.put<AgentConfirmationResponse>('/cart/update', {
      item_id: resolvedItemId,
      quantity: suggestion.quantity,
      confirmed: false,
    })
    if (suggestion.user_message) {
      confirmation.confirmation_message = `${suggestion.user_message}

${confirmation.confirmation_message}`
    }
    openConfirmationDialog(confirmation, 'put', '/cart/update', {
      item_id: resolvedItemId,
      quantity: suggestion.quantity,
      confirmed: true,
      confirmation_token: confirmation.confirmation_token,
    })
    return
  }

  if (suggestion.action === 'remove') {
    const resolvedItemId = suggestion.item_id ?? await resolveCartItemId(suggestion.product_title, userMessage)
    if (!resolvedItemId) {
      await ElMessageBox.alert(t('agent.cartTargetMissing'), t('agent.noticeTitle'), {
        confirmButtonText: t('common.close'),
        customClass: 'agent-centered-dialog',
      })
      return
    }
    const { data: confirmation } = await agentApi.delete<AgentConfirmationResponse>('/cart/remove', {
      data: {
        item_id: resolvedItemId,
        confirmed: false,
      },
    })
    if (suggestion.user_message) {
      confirmation.confirmation_message = `${suggestion.user_message}

${confirmation.confirmation_message}`
    }
    openConfirmationDialog(confirmation, 'delete', '/cart/remove', {
      item_id: resolvedItemId,
      confirmed: true,
      confirmation_token: confirmation.confirmation_token,
    })
    return
  }
}

async function resolveCartItemId(productTitle: string, userMessage: string): Promise<number | null> {
  const { data: cart } = await agentApi.get<AgentCartListResponse>('/cart')
  if (!cart.items.length) return null

  const normalize = (value: string) => String(value || '')
    .replace(/[《》\s，。、“”"'：:（）()\-]/g, '')
    .toLowerCase()

  const normalizedMessage = normalize(userMessage)
  const normalizedTarget = normalize(productTitle)

  const matchedByTitle = cart.items.filter((item) => {
    const itemTitle = normalize(item.product_title)
    if (!itemTitle) return false
    if (normalizedTarget && (itemTitle === normalizedTarget || itemTitle.includes(normalizedTarget) || normalizedTarget.includes(itemTitle))) {
      return true
    }
    return normalizedMessage.includes(itemTitle)
  })
  if (matchedByTitle.length === 1) return matchedByTitle[0].item_id

  const lowered = userMessage.toLowerCase()
  const matchedByOption = matchedByTitle.filter((item) => {
    const option = String(item.option_summary || '')
    if (lowered.includes('精装')) return option.includes('精装')
    if (lowered.includes('平装')) return option.includes('平装')
    return true
  })

  if (matchedByOption.length === 1) return matchedByOption[0].item_id
  if (!matchedByTitle.length && cart.items.length === 1) return cart.items[0].item_id
  if (cart.items.length === 1) return cart.items[0].item_id
  return null
}

function openConfirmationDialog(confirmation: AgentConfirmationResponse, method: 'post' | 'put' | 'delete', path: string, payload: Record<string, any>) {
  pendingConfirmation.value = confirmation
  pendingActionMethod.value = method
  pendingActionPath.value = path
  pendingActionPayload.value = payload
  confirmationVisible.value = true
}

async function confirmPendingAction() {
  if (!pendingConfirmation.value || !pendingActionMethod.value || !pendingActionPath.value || !pendingActionPayload.value) return
  try {
    if (pendingActionMethod.value === 'post') {
      if (Array.isArray(pendingActionPayload.value.batch)) {
        for (const payload of pendingActionPayload.value.batch) {
          await agentApi.post(pendingActionPath.value, payload)
        }
      } else {
        await agentApi.post(pendingActionPath.value, pendingActionPayload.value)
      }
    } else if (pendingActionMethod.value === 'put') {
      await agentApi.put(pendingActionPath.value, pendingActionPayload.value)
    } else {
      await agentApi.delete(pendingActionPath.value, { data: pendingActionPayload.value })
    }
    confirmationVisible.value = false
    pendingConfirmation.value = null
    pendingActionMethod.value = null
    pendingActionPath.value = ''
    pendingActionPayload.value = null
    ElMessage.success(t('agent.cartActionSuccess'))
  } catch (e:any) {
    ElMessage.error(extractErrorMessage(e, t('agent.failed')))
  }
}

function cancelPendingConfirmation() {
  confirmationVisible.value = false
  pendingConfirmation.value = null
  pendingActionMethod.value = null
  pendingActionPath.value = ''
  pendingActionPayload.value = null
  ElMessage.info(t('agent.cartActionCancelled'))
}

function resetConversation() {
  conversationId.value = ''
  messages.value = []
  draft.value = ''
}
</script>

<style scoped>
.agent-fab {
  position: fixed;
  right: 24px;
  bottom: 28px;
  width: 56px;
  height: 56px;
  border: 0;
  box-shadow: 0 16px 36px rgba(24, 52, 110, 0.22);
  z-index: 40;
}

.assistant-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
}

.assistant-tip {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.agent-guide-card {
  position: relative;
  overflow: hidden;
  padding: 16px 16px 14px;
  border-radius: 18px;
  background: linear-gradient(145deg, #6a5cff 0%, #8f7cff 45%, #b39cff 100%);
  color: #fff;
  box-shadow: 0 14px 30px rgba(106, 92, 255, 0.26);
}

.agent-guide-card::after {
  content: '';
  position: absolute;
  right: -28px;
  top: -24px;
  width: 112px;
  height: 112px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.3) 0%, rgba(255, 255, 255, 0) 70%);
}

.agent-guide-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.agent-guide-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  cursor: pointer;
}

.agent-guide-toggle {
  color: #fff;
  padding: 4px 0;
}

.agent-guide-toggle:hover,
.agent-guide-toggle:focus {
  color: #fff;
}

.agent-guide-title {
  margin-top: 10px;
  font-size: 17px;
  font-weight: 700;
}

.agent-guide-text {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.92);
}

.agent-guide-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-guide-item {
  padding: 9px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 12px;
  line-height: 1.5;
}

.assistant-messages {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 2px;
}

.assistant-msg {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.assistant-msg.user {
  align-items: flex-end;
}

.assistant-role {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.assistant-bubble {
  max-width: 88%;
  padding: 12px 14px;
  border-radius: 16px;
  background: linear-gradient(135deg, #f4f7ff 0%, #eaf0ff 100%);
  border: 1px solid rgba(24, 52, 110, 0.08);
  line-height: 1.6;
  white-space: pre-wrap;
}

.assistant-msg.user .assistant-bubble {
  background: linear-gradient(135deg, #18346e 0%, #2d5cb5 100%);
  color: #fff;
}

.assistant-actions {
  display: flex;
  justify-content: space-between;
}

.agent-confirm-message {
  line-height: 1.7;
  text-align: center;
  color: var(--el-text-color-primary);
  padding: 18px 8px 8px;
}

.agent-confirm-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
}

@media (max-width: 768px) {
  .agent-fab {
    right: 16px;
    bottom: 18px;
  }
}
</style>
