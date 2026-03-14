import { createI18n } from 'vue-i18n'
import zh from './zh.json'
import en from './en.json'
import zhTW from './zh-TW.json'
import ja from './ja.json'

const i18n = createI18n({
  legacy: false,
  locale: localStorage.getItem('lang') || 'zh',
  fallbackLocale: 'zh',
  messages: { zh, en, 'zh-TW': zhTW, ja }
})

export default i18n
