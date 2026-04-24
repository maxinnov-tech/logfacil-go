<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import {
  LayoutDashboard, FileText, Settings, Monitor, Download,
  Search, ShieldAlert, ShieldCheck, RefreshCw, FolderOpen,
  AlertTriangle, Activity, Wifi, FileDown, Trash2,
  ChevronRight, Map, PanelLeftClose, PanelLeftOpen,
  Pause, Play, Bookmark, X, ChevronUp, ChevronDown, Info, Heart
} from 'lucide-vue-next'
import {
  GetSettings, SaveSettings, IsAdmin, RestartAsAdmin,
  GetPDVsFromLog, GetServiceStatuses, RestartComponent,
  GetExportFolders, ExportLogs, ChooseFolder, ExportPDVsCSV, GetIP, GetLogMarkers,
  CheckForUpdates, DownloadAndInstallUpdate, GetAppVersion 
} from '../wailsjs/go/main/App'
import { EventsOn } from '../wailsjs/runtime/runtime'

import logoBlue from './assets/logo_blue.png'
import logoGreen from './assets/logo_green.png'

// ─── Navegação ─────────────────────────────────────────────────────────────
const currentView = ref('dashboard')
const sidebarCollapsed = ref(false)

// ─── Configurações ─────────────────────────────────────────────────────────
const settings = ref({
  last_folder: '', appearance_mode: 'dark', ui_theme: 'blue',
  auto_update: true, font_size: 13, scan_interval: 2.0, max_view_lines: 1000
})
const appVersion = ref('0.0.0')

// ─── Estado Global ─────────────────────────────────────────────────────────
const isAdmin = ref(false)
const pdvs = ref([])
const logMsg = ref('')
const localIP = ref('127.0.0.1')
const loading = ref(false)
const components = ref([])
const logMarkers = ref([])
const monitorInterval = ref(null)

// ─── Atualização Global ──────────────────────────────────────────────────
const checkUpdateLoading = ref(false)
const updateInfo = ref(null)
const showUpdateModal = ref(false)
const showAboutModal = ref(false)
const updateProgress = ref(0)
const updateBytesStr = ref('')
const isUpdating = ref(false)
const updateError = ref('')

// ─── Temas ─────────────────────────────────────────────────────────────────
const themeClass = computed(() => {
  const mode = settings.value.appearance_mode
  const theme = settings.value.ui_theme
  
  let classes = []
  
  if (mode === 'light') classes.push('theme-light')
  else if (mode === 'system') {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      classes.push('theme-light')
    }
  }
  
  if (theme === 'green') classes.push('accent-green')
  
  return classes.join(' ')
})

const appLogo = computed(() => settings.value.ui_theme === 'green' ? logoGreen : logoBlue)

// ─── Export ────────────────────────────────────────────────────────────────
const exportFolders = ref([])
const selectedFolders = ref([])
const exportPeriod = ref('7')
const customDateStart = ref('')
const customDateEnd = ref('')

// ─────────────────────────────────────────────────────────────────────────────
// LOG STATE
// ─────────────────────────────────────────────────────────────────────────────
const serviceLogs = ref({})      // buffer ativo
const pausedLines = ref({})      // buffer durante pausa
const activeLogTab = ref('')
const logContainerRef = ref(null)
const tabsContainerRef = ref(null)
const isFollowing = ref(true)

// Buffer de batching: acumula linhas por serviço antes de aplicar na UI
const pendingLines = {}          // { service: [linhas...] } - buffer temporário
let batchFlushTimer = null       // timer de flush

// ─── Marcador / Custom Highlight ───
const customHighlightTerm = ref('')
const HIGHLIGHT_COLOR = '#4dabf7'

// ─── Busca Incremental (Ctrl+F) ─
const showLogSearch = ref(false)
const logSearchQuery = ref('')
const logSearchInputRef = ref(null)
const currentMatchIdx = ref(0)
const caseSensitive = ref(false)

// ─── Minimap ───────────────────────────
const showMinimap = ref(true)
const minimapRef = ref(null)
const logScrollTop = ref(0)
const logScrollHeight = ref(1)
const logClientHeight = ref(1)

// ─── Computed ──────────────────────────────────────────────────────────────
const activeLogsCount = computed(() => Object.keys(serviceLogs.value).length)

const criticalAlerts = ref(0)
const errorPatterns = computed(() => {
  if (!logMarkers.value.length) return []
  const errorStyles = ['exception', 'error']
  return logMarkers.value
    .filter(m => errorStyles.includes(m.level))
    .map(m => m.pattern.toUpperCase())
})

function checkErrorInLines(lines) {
  let count = 0
  const patterns = errorPatterns.value
  if (!patterns.length) return 0
  
  for (const line of lines) {
    const upperLine = line.toUpperCase()
    for (const p of patterns) {
      if (upperLine.includes(p)) {
        count++
        break
      }
    }
  }
  return count
}

const currentLines = computed(() =>
  (activeLogTab.value && serviceLogs.value[activeLogTab.value])
    ? serviceLogs.value[activeLogTab.value]
    : []
)

const unreadCount = computed(() =>
  (!activeLogTab.value || isFollowing.value) ? 0
    : (pausedLines.value[activeLogTab.value] || []).length
)

const matchedLineIndices = computed(() => {
  if (!logSearchQuery.value) return []
  const q = caseSensitive.value ? logSearchQuery.value : logSearchQuery.value.toLowerCase()
  return currentLines.value
    .map((line, idx) => ({ line: caseSensitive.value ? line : line.toLowerCase(), idx }))
    .filter(({ line }) => line.includes(q))
    .map(({ idx }) => idx)
})

// Reseta índice ao mudar o termo ou aba
watch(logSearchQuery, () => { currentMatchIdx.value = 0 })
watch(caseSensitive,  () => { currentMatchIdx.value = 0 })
watch(activeLogTab,   () => { currentMatchIdx.value = 0; logSearchQuery.value = '' })

// ─── Minimap helpers ───────────────────────────────────────────────────────
function getMinimapColor(line) {
  const l = line.toUpperCase()
  for (const m of logMarkers.value) {
    if (l.includes(m.pattern.toUpperCase())) {
      return m.color || '#555'
    }
  }
  if (customHighlightTerm.value && line.toLowerCase().includes(customHighlightTerm.value.toLowerCase())) return '#3498db'
  return null
}

const viewportStyle = computed(() => {
  const total = logScrollHeight.value, client = logClientHeight.value
  if (total <= client || total <= 0) return { top: '0%', height: '100%' }
  return {
    top:    ((logScrollTop.value / total)  * 100).toFixed(2) + '%',
    height: (Math.max(client / total, 0.05) * 100).toFixed(2) + '%'
  }
})

const mmLineH = computed(() => {
  const n = currentLines.value.length
  return n > 800 ? 1 : n > 400 ? 1.5 : 2
})

// ─── Syntax Highlighting ──────────────────────────────────────────────────
function getLineClass(line) {
  const l = line.toUpperCase()
  for (const m of logMarkers.value) {
    if (l.includes(m.pattern.toUpperCase())) {
      if (m.level === 'exception') return 'log-exception'
      if (m.level === 'error') return 'log-error'
      if (m.level === 'warn') return 'log-warn-strong'
      if (m.level === 'info') return 'log-info'
      if (m.level === 'debug') return 'log-debug'
    }
  }
  return 'log-default'
}

function getLineColor(line) {
  const l = line.toUpperCase()
  for (const m of logMarkers.value) {
    if (l.includes(m.pattern.toUpperCase())) {
      return m.color
    }
  }
  return null
}

function getLineParts(line, lineIdx) {
  const searchQ = logSearchQuery.value
  const markerQ = customHighlightTerm.value
  if (!searchQ && !markerQ) return null

  const activeQuery = searchQ || markerQ
  const isSearch = !!searchQ
  const qLower = caseSensitive.value ? activeQuery : activeQuery.toLowerCase()
  const lineLower = caseSensitive.value ? line : line.toLowerCase()

  const parts = []
  let pos = 0
  let hasMatch = false
  while (pos < line.length) {
    const idx = lineLower.indexOf(qLower, pos)
    if (idx < 0) { parts.push({ text: line.slice(pos), type: 'normal' }); break }
    if (idx > pos) parts.push({ text: line.slice(pos, idx), type: 'normal' })
    const isCurrentLine = isSearch && matchedLineIndices.value[currentMatchIdx.value] === lineIdx
    parts.push({
      text: line.slice(idx, idx + activeQuery.length),
      type: isSearch ? (isCurrentLine ? 'current' : 'search') : 'marker'
    })
    hasMatch = true
    pos = idx + activeQuery.length
  }
  return hasMatch ? parts : null
}

// ─── Scroll ────────────────────────────────────────────────────────────────
function updateMetrics() {
  if (!logContainerRef.value) return
  const el = logContainerRef.value
  logScrollTop.value  = el.scrollTop
  logScrollHeight.value = el.scrollHeight
  logClientHeight.value = el.clientHeight
}

function scrollToBottom() {
  nextTick(() => {
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
      updateMetrics()
    }
  })
}

function handleLogScroll(e) {
  const el = e.target
  logScrollTop.value  = el.scrollTop
  logScrollHeight.value = el.scrollHeight
  logClientHeight.value = el.clientHeight
  if (isFollowing.value && el.scrollTop + el.clientHeight < el.scrollHeight - 50) {
    isFollowing.value = false
  }
}

function handleTabsWheel(e) {
  if (!tabsContainerRef.value) return
  tabsContainerRef.value.scrollLeft += e.deltaY
}

function scrollToActiveTab(svc) {
  activeLogTab.value = svc
  scrollToBottom()
  nextTick(() => {
    const activeEl = tabsContainerRef.value?.querySelector('.tab-active')
    if (activeEl) {
      activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
    }
  })
}

function handleMinimapClick(ev) {
  if (!minimapRef.value || !logContainerRef.value) return
  const rect = minimapRef.value.getBoundingClientRect()
  const frac = Math.max(0, Math.min(1, (ev.clientY - rect.top) / rect.height))
  logContainerRef.value.scrollTop = frac * (logContainerRef.value.scrollHeight - logContainerRef.value.clientHeight)
  if (isFollowing.value) isFollowing.value = false
}

// ─── Buffers ───────────────────────────────────────────────────────────────
function flushPausedLines() {
  const max = settings.value.max_view_lines || 1000
  for (const [svc, lines] of Object.entries(pausedLines.value)) {
    if (!serviceLogs.value[svc]) serviceLogs.value[svc] = []
    serviceLogs.value[svc].push(...lines)
    if (serviceLogs.value[svc].length > max)
      serviceLogs.value[svc] = serviceLogs.value[svc].slice(-max)
  }
  pausedLines.value = {}
}

function toggleFollow() {
  isFollowing.value = !isFollowing.value
  if (isFollowing.value) {
    flushPausedLines()
    scrollToBottom()
  }
}

function addLines(svc, lines) {
  const max = settings.value.max_view_lines || 1000
  if (!serviceLogs.value[svc]) {
    serviceLogs.value[svc] = []
    if (!activeLogTab.value) activeLogTab.value = svc
  }
  
  // Atualiza contador de erros antes de adicionar (apenas para as novas)
  const newErrors = checkErrorInLines(lines)
  criticalAlerts.value += newErrors

  serviceLogs.value[svc].push(...lines)
  
  if (serviceLogs.value[svc].length > max) {
    const evicted = serviceLogs.value[svc].slice(0, serviceLogs.value[svc].length - max)
    // Decrementa erros das linhas que saíram do buffer
    const evictedErrors = checkErrorInLines(evicted)
    criticalAlerts.value = Math.max(0, criticalAlerts.value - evictedErrors)
    serviceLogs.value[svc] = serviceLogs.value[svc].slice(-max)
  }
}

function searchNext() {
  if (!matchedLineIndices.value.length) return
  currentMatchIdx.value = (currentMatchIdx.value + 1) % matchedLineIndices.value.length
  scrollToMatch()
}
function searchPrev() {
  if (!matchedLineIndices.value.length) return
  currentMatchIdx.value = (currentMatchIdx.value - 1 + matchedLineIndices.value.length) % matchedLineIndices.value.length
  scrollToMatch()
}
function scrollToMatch() {
  nextTick(() => {
    const lineIdx = matchedLineIndices.value[currentMatchIdx.value]
    const el = document.getElementById(`ll-${lineIdx}`)
    if (el) { el.scrollIntoView({ block: 'center', behavior: 'smooth' }); updateMetrics() }
  })
}

function handleKey(ev) {
  if (currentView.value !== 'logs') return
  if (ev.key === 'F2') { ev.preventDefault(); toggleFollow(); return }
  if (ev.ctrlKey && ev.key.toLowerCase() === 'f') {
    ev.preventDefault(); showLogSearch.value = true
    nextTick(() => logSearchInputRef.value?.focus())
    if (isFollowing.value) toggleFollow()
    return
  }
  if (ev.key === 'Escape' && showLogSearch.value) {
    showLogSearch.value = false; logSearchQuery.value = ''; return
  }
  if (showLogSearch.value) {
    if (ev.key === 'Enter') { ev.preventDefault(); ev.shiftKey ? searchPrev() : searchNext() }
    if (ev.key === 'ArrowDown') { ev.preventDefault(); searchNext() }
    if (ev.key === 'ArrowUp') { ev.preventDefault(); searchPrev() }
  }
}

// ─── Data loading ──────────────────────────────────────────────────────────
async function loadInitialData() {
  const s = await GetSettings(); if (s) settings.value = s
  isAdmin.value = await IsAdmin()
  localIP.value = await GetIP()
  logMarkers.value = await GetLogMarkers()
  appVersion.value = await GetAppVersion()
  refreshDashboard()
  loadExportData()
}

async function refreshDashboard() {
  loading.value = true
  try {
    const r = await GetPDVsFromLog()
    pdvs.value = r?.pdvs || []; logMsg.value = r?.message || ''
  } catch (e) { logMsg.value = 'Erro: ' + e } finally { loading.value = false }
}

async function refreshServices() { components.value = await GetServiceStatuses() }

async function handleRestartComponent(name) {
  if (!isAdmin.value) { alert('Requer privilégios de Administrador.'); return }
  loading.value = true
  try { 
    const res = await RestartComponent(name)
    if (res === true) alert(`O serviço '${name}' foi reiniciado com sucesso!`)
    else if (Array.isArray(res)) alert(res[1])
    else alert(res || "Operação concluída.")
    refreshServices() 
  }
  catch (e) { alert('Erro: ' + e) } finally { loading.value = false }
}

async function loadExportData() { exportFolders.value = await GetExportFolders() }

async function handleExport() {
  if (!selectedFolders.value.length) { alert('Selecione ao menos uma pasta.'); return }
  loading.value = true
  try { 
    const res = await ExportLogs(selectedFolders.value, exportPeriod.value, customDateStart.value, customDateEnd.value)
    alert(Array.isArray(res) ? res[1] : res)
  }
  catch (e) { alert('Erro: ' + e) } finally { loading.value = false }
}

async function handleExportPDVsCSV() {
  if (!pdvs.value.length) { alert('Nenhum PDV disponível.'); return }
  loading.value = true
  try { 
    const res = await ExportPDVsCSV(pdvs.value)
    alert(Array.isArray(res) ? res[1] : res)
  }
  catch (e) { alert('Erro: ' + e) } finally { loading.value = false }
}

async function handleSaveSettings() {
  try {
    await SaveSettings(settings.value)
    const saved = await GetSettings(); if (saved) settings.value = saved
  } catch(e) { alert('Erro ao salvar: ' + e) }
}

async function handleChooseFolder() {
  try {
    const f = await ChooseFolder()
    if (f) { settings.value.last_folder = f; await loadExportData() }
  } catch(e) { alert('Erro ao selecionar pasta: ' + e) }
}

function clearLogTab(svc) {
  if (serviceLogs.value[svc]) {
    const errors = checkErrorInLines(serviceLogs.value[svc])
    criticalAlerts.value = Math.max(0, criticalAlerts.value - errors)
    serviceLogs.value[svc] = []
  }
  if (pausedLines.value[svc]) pausedLines.value[svc] = []
}

watch(currentView, val => {
  if (val === 'monitor') {
    refreshServices()
    monitorInterval.value = setInterval(refreshServices, 3000)
  } else {
    if (monitorInterval.value) { clearInterval(monitorInterval.value); monitorInterval.value = null }
  }
  if (val === 'export')    loadExportData()
  if (val === 'dashboard') refreshDashboard()
})

async function handleCheckUpdates() {
  checkUpdateLoading.value = true
  updateError.value = ''
  try {
    const res = await CheckForUpdates()
    if (res.has_update) { updateInfo.value = res; showUpdateModal.value = true }
    else alert(res.message || 'O sistema já está na última versão.')
  } catch (err) { alert('Erro ao buscar atualização: ' + err) }
  finally { checkUpdateLoading.value = false }
}

async function startUpdateDownload() {
  if (!updateInfo.value || !updateInfo.value.download_url) return
  isUpdating.value = true
  updateError.value = ''; updateProgress.value = 0
  try { await DownloadAndInstallUpdate(updateInfo.value.download_url) }
  catch(err) { updateError.value = "Erro no Update: " + err; isUpdating.value = false }
}

onMounted(() => {
  window.addEventListener('keydown', handleKey)

  // ─── Registra listeners ANTES de qualquer chamada async ────────────────────
  // O backend espera 2s antes de emitir eventos - garante que chegamos antes.

  // Flush de logs em lote: a cada 50ms aplica tudo que acumulou
  batchFlushTimer = setInterval(() => {
    if (!Object.keys(pendingLines).length) return
    for (const [svc, lines] of Object.entries(pendingLines)) {
      if (!lines.length) continue
      if (!isFollowing.value) {
        if (!pausedLines.value[svc]) pausedLines.value[svc] = []
        pausedLines.value[svc].push(...lines)
      } else {
        addLines(svc, lines)
        if (activeLogTab.value === svc) { scrollToBottom(); nextTick(updateMetrics) }
      }
      delete pendingLines[svc]
    }
  }, 50)

  EventsOn('service-log-append', update => {
    if (!update?.service) return
    const lines = update.content.split('\n').filter(l => l.trim())
    if (!lines.length) return
    // Acumula no buffer temporário (sem toque na UI)
    if (!pendingLines[update.service]) pendingLines[update.service] = []
    pendingLines[update.service].push(...lines)
  })

  EventsOn('ip-updated', ip => { if (ip) localIP.value = ip })
  EventsOn('update-available', res => { updateInfo.value = res; showUpdateModal.value = true })
  EventsOn('update-progress', prog => {
    updateProgress.value = prog.percent
    if (prog.total > 1024 * 1024) updateBytesStr.value = `${(prog.downloaded / (1024*1024)).toFixed(1)} / ${(prog.total / (1024*1024)).toFixed(1)} MB`
    else updateBytesStr.value = `${(prog.downloaded / 1024).toFixed(1)} / ${(prog.total / 1024).toFixed(1)} KB`
  })

  // Carrega dados iniciais DEPOIS de registrar os listeners
  loadInitialData()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKey)
  if (monitorInterval.value) clearInterval(monitorInterval.value)
  if (batchFlushTimer) clearInterval(batchFlushTimer)
})
</script>

<template>
  <div :class="['flex h-screen overflow-hidden', themeClass]">
    <!-- Menu Lateral Sidebar -->
    <aside :class="['glass-panel m-3 flex flex-col transition-all duration-300 ease-in-out z-50 flex-shrink-0',
                   sidebarCollapsed ? 'w-16' : 'w-56']">
      <div class="p-4 flex items-center gap-3 border-b border-theme relative min-h-[64px]">
        <div class="w-8 h-8 flex items-center justify-center">
          <img :src="appLogo" class="w-full h-full object-contain" alt="Logo" />
        </div>
        <div v-if="!sidebarCollapsed" class="flex flex-col overflow-hidden">
          <span class="text-sm font-black text-primary tracking-tighter truncate">LogFácil <span class="text-accent">Pro</span></span>
          <span class="text-[8px] text-muted font-bold uppercase tracking-widest -mt-1">v{{ appVersion }}</span>
        </div>
        <button @click="sidebarCollapsed = !sidebarCollapsed" 
          class="absolute -right-3 top-7 w-6 h-6 bg-theme-10 border border-theme rounded-full flex items-center justify-center hover:bg-accent hover:text-white transition-all z-10">
          <PanelLeftClose v-if="!sidebarCollapsed" class="w-3.5 h-3.5" />
          <PanelLeftOpen v-else class="w-3.5 h-3.5" />
        </button>
      </div>

      <nav class="flex-1 p-2 space-y-1.5 overflow-y-auto tabs-hide-scroll">
        <button v-for="item in [
          { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
          { id: 'logs', label: 'Monitor de Logs', icon: FileText },
          { id: 'monitor', label: 'Serviços PDV', icon: Monitor },
          { id: 'export', label: 'Exportar', icon: Download }
        ]" :key="item.id"
          @click="currentView = item.id"
          :class="['w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl transition-all text-xs',
                   sidebarCollapsed ? 'justify-center' : '',
                   currentView === item.id ? 'bg-accent text-white font-bold shadow-lg shadow-accent/20' : 'hover:bg-theme-10 text-secondary hover:text-primary']">
          <component :is="item.icon" class="w-4 h-4 flex-shrink-0" />
          <span v-if="!sidebarCollapsed" class="font-medium whitespace-nowrap">{{ item.label }}</span>
        </button>
      </nav>

      <div class="p-2 border-t border-theme space-y-1">
        <button @click="currentView = 'settings'"
          :class="['w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl text-xs transition-all',
                   sidebarCollapsed ? 'justify-center' : '',
                   currentView === 'settings' ? 'bg-accent-10 text-accent font-bold' : 'hover:bg-theme-10 text-secondary']">
          <Settings class="w-4 h-4 flex-shrink-0" />
          <span v-if="!sidebarCollapsed" class="font-medium">Configurações</span>
        </button>

        <div v-if="!sidebarCollapsed" class="mt-2 group">
          <div v-if="!isAdmin" class="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl">
            <div class="flex items-center gap-2 text-amber-500 mb-2 text-[10px] font-black uppercase tracking-widest">
              <ShieldAlert class="w-3.5 h-3.5" /> RESTRITO
            </div>
            <button @click="RestartAsAdmin()" class="w-full py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-900 font-bold rounded-lg text-[10px] transition-all">AUTORIZAR</button>
          </div>
          <div v-else class="flex items-center gap-2 px-3 py-2.5 text-[10px] text-green-500 bg-green-500/10 border border-green-500/20 rounded-xl">
            <ShieldCheck class="w-4 h-4" /><span class="font-black uppercase tracking-widest">ADMINISTRADOR</span>
          </div>
        </div>
        <div v-else class="flex justify-center py-2 mt-1">
          <div :class="['w-8 h-8 rounded-xl flex items-center justify-center transition-all', isAdmin ? 'bg-green-500/10 text-green-500' : 'bg-amber-500/10 text-amber-500']">
            <ShieldCheck v-if="isAdmin" class="w-4 h-4" /><ShieldAlert v-else class="w-4 h-4" />
          </div>
        </div>
      </div>
    </aside>

    <main class="flex-1 flex flex-col m-3 ml-0 overflow-hidden min-w-0">
      <header class="h-12 glass-panel mb-3 px-4 flex items-center justify-between flex-shrink-0">
        <div class="flex items-center gap-2">
          <ChevronRight class="w-3 h-3 text-muted" />
          <h2 class="text-xs font-bold text-primary uppercase tracking-widest">
            {{ { dashboard:'Dashboard', logs:'Monitor de Logs', monitor:'Serviços PDV', export:'Exportar Logs', settings:'Configurações' }[currentView] }}
          </h2>
          <div v-if="loading" class="animate-spin text-accent ml-1"><RefreshCw class="w-3 h-3" /></div>
        </div>
        <div class="flex items-center gap-3">
          <span v-if="currentView === 'logs'" class="hidden sm:flex items-center gap-1 text-[9px] text-muted border border-theme px-2 py-1 rounded font-mono">F2 Pausar · Ctrl+F Buscar</span>
          <span class="text-[9px] text-muted font-mono hidden md:block">v{{ appVersion }}</span>
        </div>
      </header>

      <section :class="['flex-1 glass-panel relative min-h-0', currentView === 'logs' ? 'overflow-hidden flex flex-col p-3' : 'overflow-y-auto p-5']">
        <transition name="vfade" mode="out-in">
          <div :key="currentView" class="h-full flex flex-col">
            <!-- DASHBOARD -->
            <div v-if="currentView === 'dashboard'" class="space-y-4">
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div class="glass-card p-5 group hover:border-accent/30 transition-all">
                  <div class="flex items-start justify-between">
                    <div>
                      <p class="text-[10px] text-muted uppercase tracking-widest font-bold">PDVs em Operação</p>
                      <div class="text-3xl font-black mt-2 tabular-nums text-primary">{{ pdvs.length }}</div>
                    </div>
                    <div class="w-10 h-10 bg-accent-10 rounded-xl flex items-center justify-center"><Monitor class="w-5 h-5 text-accent" /></div>
                  </div>
                  <div class="mt-4 text-[10px] text-green-500 font-bold flex items-center gap-1.5"><span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span> Monitorando</div>
                </div>
                <div class="glass-card p-5 group hover:border-accent/30 transition-all">
                  <div class="flex items-start justify-between">
                    <div>
                      <p class="text-[10px] text-muted uppercase tracking-widest font-bold">Alertas Críticos</p>
                      <div :class="['text-3xl font-black mt-2 tabular-nums', criticalAlerts > 0 ? 'text-rose-500' : 'text-primary']">{{ criticalAlerts }}</div>
                    </div>
                    <div :class="['w-10 h-10 rounded-xl flex items-center justify-center', criticalAlerts > 0 ? 'bg-rose-500/10' : 'bg-theme-10']"><AlertTriangle :class="['w-5 h-5', criticalAlerts > 0 ? 'text-rose-400' : 'text-muted']" /></div>
                  </div>
                  <p class="mt-4 text-[10px] text-muted font-medium italic">{{ criticalAlerts === 0 ? 'Nenhum erro detectado' : `${criticalAlerts} ocorrência(s) detectada(s)` }}</p>
                </div>
                <div class="glass-card p-5 group hover:border-accent/30 transition-all">
                  <div class="flex items-start justify-between">
                    <div>
                      <p class="text-[10px] text-muted uppercase tracking-widest font-bold">Logs Ativos</p>
                      <div class="text-3xl font-black mt-2 tabular-nums text-primary">{{ activeLogsCount }}</div>
                    </div>
                    <div class="w-10 h-10 bg-purple-500/10 rounded-xl flex items-center justify-center"><FileText class="w-5 h-5 text-purple-400" /></div>
                  </div>
                  <div class="mt-4 text-[10px] text-accent font-bold flex items-center gap-1.5"><Wifi class="w-3.5 h-3.5" /> API LOCAL {{ localIP }}:8080</div>
                </div>
              </div>
              <div class="glass-card overflow-hidden">
                <div class="p-3 border-b border-white/10 flex items-center justify-between">
                  <h3 class="font-semibold text-xs">Atividade Recente dos PDVs</h3>
                  <div class="flex items-center gap-4">
                    <button @click="handleExportPDVsCSV" :disabled="!pdvs.length" class="text-[10px] text-muted hover:text-accent flex items-center gap-1 disabled:opacity-30"><FileDown class="w-3 h-3" /> Exportar CSV</button>
                    <button @click="refreshDashboard" class="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-1"><RefreshCw class="w-3 h-3" :class="{'animate-spin': loading}" /> Atualizar</button>
                  </div>
                </div>
                <div class="overflow-x-auto">
                  <table class="w-full text-left text-[11px]">
                    <thead class="bg-white/5">
                      <tr><th class="p-2.5 font-medium text-secondary">Código</th><th class="p-2.5 font-medium text-secondary">ID Interno</th><th class="p-2.5 font-medium text-secondary">Nome</th><th class="p-2.5 font-medium text-secondary">IP</th><th class="p-2.5 font-medium text-secondary">Status</th></tr>
                    </thead>
                    <tbody class="divide-y divide-white/5">
                      <tr v-for="p in pdvs" :key="p.id_interno" class="hover:bg-white/5 transition-colors">
                        <td class="p-2.5 font-mono text-accent">{{ p.codigo }}</td><td class="p-2.5 text-muted">{{ p.id_interno }}</td><td class="p-2.5">{{ p.nome }}</td><td class="p-2.5 text-secondary">{{ p.ip }}</td>
                        <td class="p-2.5"><span class="px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded text-[9px] font-medium">Ativo</span></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <!-- LOG VIEW -->
            <div v-if="currentView === 'logs'" class="h-full flex flex-col overflow-hidden">
              <div class="flex items-center justify-between mb-2 flex-shrink-0 gap-2">
                <div class="flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg flex-1 max-w-xs">
                  <Bookmark class="w-3 h-3 text-accent flex-shrink-0" /><span class="text-[9px] text-muted font-bold flex-shrink-0">MARCADOR</span>
                  <input v-model="customHighlightTerm" placeholder="Termo para destacar..." class="bg-transparent text-xs outline-none placeholder:text-muted text-primary flex-1 min-w-0">
                  <button v-if="customHighlightTerm" @click="customHighlightTerm = ''" class="text-muted hover:text-primary"><X class="w-3 h-3" /></button>
                </div>
                <div class="flex items-center gap-2 flex-shrink-0">
                  <button @click="showMinimap = !showMinimap" :class="['px-2 py-1.5 rounded-lg border text-[10px] font-medium transition-all', showMinimap ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' : 'bg-white/5 border-white/10 text-slate-500']"><Map class="w-3 h-3" /></button>
                </div>
              </div>
              <div ref="tabsContainerRef" @wheel.passive="handleTabsWheel" class="flex gap-0.5 mb-1 border-b border-theme flex-shrink-0 pb-px tabs-hide-scroll overflow-x-auto select-none">
                <button v-for="(lines, svc) in serviceLogs" :key="svc" @click="scrollToActiveTab(svc)" :class="['px-3 py-1.5 rounded-t text-[10px] font-bold whitespace-nowrap border-b-2 flex items-center gap-1.5 transition-all flex-shrink-0', activeLogTab === svc ? 'bg-accent-10 text-accent border-accent tab-active' : 'text-secondary border-transparent hover:text-primary hover:bg-theme-10']">
                  <span class="w-1.5 h-1.5 rounded-full" :class="activeLogTab === svc ? 'bg-accent' : 'bg-muted'"></span>{{ svc }}
                  <span v-if="!isFollowing && (pausedLines[svc] || []).length" class="px-1 py-0.5 rounded text-[8px] font-bold" :style="{ backgroundColor: 'var(--status-warning-bg)', color: 'var(--status-warning)' }">+{{ (pausedLines[svc] || []).length }}</span>
                </button>
              </div>
              <div class="flex flex-1 min-h-0 gap-2">
                <div ref="logContainerRef" @scroll="handleLogScroll" class="flex-1 min-w-0 rounded-lg border border-white/5 overflow-y-auto px-3 py-2 log-terminal" :style="{ fontSize: (settings.font_size || 13) + 'px', fontFamily: 'Consolas, monospace', lineHeight: '1.5' }">
                  <template v-if="activeLogTab && serviceLogs[activeLogTab]">
                    <div v-for="(line, idx) in currentLines" :key="idx" :id="`ll-${idx}`" :class="['group flex items-start gap-2 px-1 py-px rounded hover:bg-white/5', getLineClass(line), matchedLineIndices[currentMatchIdx] === idx && logSearchQuery ? 'ring-1 ring-blue-500/30' : '']" :style="{ color: getLineColor(line) }">
                      <span class="select-none text-[9px] text-slate-700 w-8 text-right flex-shrink-0 pt-px">{{ idx + 1 }}</span>
                      <span class="break-all whitespace-pre-wrap flex-1 min-w-0">
                        <template v-if="!logSearchQuery && !customHighlightTerm">{{ line }}</template>
                        <template v-else-if="getLineParts(line, idx)">
                          <template v-for="(part, pi) in getLineParts(line, idx)">
                            <mark v-if="part.type === 'search'" :key="'s'+pi" class="hl-search">{{ part.text }}</mark>
                            <mark v-else-if="part.type === 'current'" :key="'c'+pi" class="hl-current">{{ part.text }}</mark>
                            <mark v-else-if="part.type === 'marker'" :key="'m'+pi" class="hl-marker">{{ part.text }}</mark>
                            <span v-else :key="'n'+pi">{{ part.text }}</span>
                          </template>
                        </template>
                        <template v-else>{{ line }}</template>
                      </span>
                    </div>
                  </template>
                  <div v-else class="h-full flex flex-col items-center justify-center text-slate-700 gap-2">
                    <FileText class="w-8 h-8 opacity-30" /><span class="text-xs">Selecione uma aba para visualizar o log.</span>
                  </div>
                </div>
                <div v-if="showMinimap && activeLogTab" ref="minimapRef" @click="handleMinimapClick" class="minimap-panel">
                  <div class="minimap-viewport" :style="viewportStyle"></div>
                  <template v-for="(line, idx) in currentLines"><div v-if="getMinimapColor(line)" :key="'mm-'+idx" class="minimap-strip" :style="{ height: mmLineH + 'px', background: getMinimapColor(line) }"></div><div v-else :key="'mme-'+idx" class="minimap-strip-empty" :style="{ height: mmLineH + 'px' }"></div></template>
                </div>
              </div>
              <transition name="slide-up">
                <div v-if="showLogSearch" class="flex items-center gap-2 mt-1.5 flex-shrink-0 px-2 py-1.5 bg-theme-10 border border-accent/30 rounded-lg">
                  <Search class="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                  <input ref="logSearchInputRef" v-model="logSearchQuery" @keydown.enter.exact.prevent="searchNext" @keydown.shift.enter.prevent="searchPrev" placeholder="Buscar nos logs..." class="flex-1 bg-transparent text-xs outline-none text-primary placeholder:text-muted">
                  <span class="text-[10px] font-mono text-muted flex-shrink-0 w-14 text-right">{{ matchedLineIndices.length > 0 ? `${currentMatchIdx + 1}/${matchedLineIndices.length}` : '0/0' }}</span>
                  <label class="flex items-center gap-1 text-[9px] text-muted cursor-pointer flex-shrink-0"><input type="checkbox" v-model="caseSensitive" class="w-3 h-3 accent-accent"> Aa</label>
                  <button @click="searchPrev" :disabled="!matchedLineIndices.length" class="p-1 hover:bg-white/10 rounded disabled:opacity-30"><ChevronUp class="w-3.5 h-3.5" /></button>
                  <button @click="searchNext" :disabled="!matchedLineIndices.length" class="p-1 hover:bg-white/10 rounded disabled:opacity-30"><ChevronDown class="w-3.5 h-3.5" /></button>
                  <button @click="showLogSearch = false; logSearchQuery = ''" class="p-1 bg-rose-600/20 text-rose-400 rounded"><X class="w-3.5 h-3.5" /></button>
                </div>
              </transition>
              <div v-if="activeLogTab" class="flex items-center justify-between mt-1.5 pt-1.5 border-t border-white/5 flex-shrink-0">
                <div class="flex items-center gap-2">
                  <button @click="toggleFollow" :class="['px-3 py-1.5 rounded-lg text-[10px] font-bold flex items-center gap-1.5 border', isFollowing ? 'bg-blue-600 text-white border-blue-500' : '']" :style="!isFollowing ? { backgroundColor: 'var(--status-warning-bg)', color: 'var(--status-warning)', borderColor: 'var(--status-warning)' } : {}">
                    {{ isFollowing ? 'Seguindo — F2' : 'Pausado — F2' }}<span v-if="!isFollowing && unreadCount > 0" class="px-1 py-0.5 rounded" :style="{ backgroundColor: 'var(--status-warning-bg)', filter: 'brightness(0.95)' }">+{{ unreadCount }}</span>
                  </button>
                  <button @click="handleRestartComponent(activeLogTab)" :disabled="loading || !isAdmin" class="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-[10px] flex items-center gap-1.5 disabled:opacity-40"><RefreshCw class="w-3 h-3" /> Reiniciar <span class="font-mono">{{ activeLogTab }}</span></button>
                </div>
                <button @click="clearLogTab(activeLogTab)" class="flex items-center gap-1 text-[10px] text-slate-500 hover:text-rose-400"><Trash2 class="w-3 h-3" /> Limpar</button>
              </div>
            </div>

            <!-- MONITOR DE SERVIÇOS -->
            <div v-if="currentView === 'monitor'" class="space-y-4">
              <div class="flex items-center justify-between"><p class="text-xs text-muted">Atualiza automaticamente a cada 3s.</p><button @click="refreshServices" class="text-xs text-accent font-bold"><RefreshCw class="w-3 h-3" /> ATUALIZAR</button></div>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <div v-for="comp in components" :key="comp.name" class="glass-card p-4 flex flex-col">
                  <div class="flex items-start justify-between mb-3">
                    <div><h3 class="font-bold text-xs text-primary uppercase">{{ comp.name }}</h3><span :class="['mt-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase', comp.is_ok ? 'bg-green-500/10 text-green-500' : 'bg-rose-500/10 text-rose-500']">{{ comp.status }}</span></div>
                    <div :class="['w-2 h-2 rounded-full mt-1', comp.is_ok ? 'bg-green-500' : 'bg-rose-500']"></div>
                  </div>
                  <div class="flex-1 space-y-1 mb-3">
                    <div v-for="svc in (comp.services || [])" :key="svc.name" class="flex items-center justify-between text-[10px] py-1 border-b border-theme last:border-0"><span class="text-secondary font-mono truncate mr-2">{{ svc.name }}</span><span :class="['font-bold text-[9px] uppercase', svc.running ? 'text-green-500' : 'text-rose-500']">{{ svc.running ? 'Running' : 'Stopped' }}</span></div>
                  </div>
                  <button @click="handleRestartComponent(comp.name)" :disabled="loading || !isAdmin" class="w-full py-2 bg-accent text-white rounded-lg text-[10px] font-bold">REINICIAR STACK</button>
                </div>
              </div>
            </div>

            <!-- EXPORTAÇÃO -->
            <div v-if="currentView === 'export'" class="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
              <div class="lg:col-span-2 glass-card flex flex-col min-h-0">
                <div class="p-3 border-b border-theme flex items-center justify-between"><h3 class="font-bold text-xs text-primary">Pastas de Logs</h3><button @click="loadExportData" class="text-[10px] text-accent font-bold uppercase">Atualizar</button></div>
                <div class="flex-1 overflow-y-auto p-3 space-y-1">
                  <label v-for="folder in exportFolders" :key="folder" class="flex items-center gap-2.5 p-2.5 bg-theme-10 rounded-lg cursor-pointer hover:bg-accent/5 overflow-hidden"><input type="checkbox" :value="folder" v-model="selectedFolders" class="w-3.5 h-3.5 accent-accent"><span class="text-xs font-mono text-secondary truncate">{{ folder }}</span></label>
                </div>
                <div class="p-2.5 border-t border-theme flex gap-3 flex-shrink-0">
                  <button @click="selectedFolders = [...exportFolders]" class="text-[10px] text-secondary hover:text-accent">Selecionar Tudo</button><button @click="selectedFolders = []" class="text-[10px] text-secondary hover:text-rose-400">Limpar</button><span class="ml-auto text-[10px] text-muted">{{ selectedFolders.length }} selecionadas</span>
                </div>
              </div>
              <div class="glass-card p-4 flex flex-col gap-4">
                <h3 class="font-bold text-xs mb-3">Período de Exportação</h3>
                <div class="space-y-2"><label v-for="p in [{n:'Hoje',v:'0'},{n:'7 dias',v:'7'},{n:'15 dias',v:'15'},{n:'30 dias',v:'30'},{n:'Tudo',v:'all'},{n:'Outro',v:'custom'}]" :key="p.v" class="flex items-center gap-2.5 cursor-pointer"><input type="radio" name="period" :value="p.v" v-model="exportPeriod" class="w-3.5 h-3.5 accent-accent"><span :class="['text-xs', exportPeriod === p.v ? 'text-accent font-medium' : 'text-secondary']">{{ p.n }}</span></label></div>
                <div v-if="exportPeriod === 'custom'" class="space-y-2 border-t border-theme pt-3">
                  <div><label class="text-[10px] text-muted">Início</label><input v-model="customDateStart" placeholder="DD/MM/AAAA" class="mt-1 w-full px-2.5 py-1.5 bg-theme-10 border border-theme rounded text-xs"></div>
                  <div><label class="text-[10px] text-muted">Fim</label><input v-model="customDateEnd" placeholder="DD/MM/AAAA" class="mt-1 w-full px-2.5 py-1.5 bg-theme-10 border border-theme rounded text-xs"></div>
                </div>
                <button @click="handleExport" :disabled="loading || !selectedFolders.length" class="mt-auto w-full py-3 bg-green-600 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2"><Download class="w-4 h-4" /> Gerar ZIP</button>
              </div>
            </div>

            <!-- CONFIGURAÇÕES -->
            <div v-if="currentView === 'settings'" class="w-full max-w-2xl mx-auto space-y-6">
              <div class="glass-card p-4 sm:p-8">
                <h3 class="text-sm font-bold mb-6 flex items-center gap-2 text-primary"><Settings class="w-4 h-4 text-accent" /> Preferências Gerais</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
                  <div class="space-y-6">
                    <div class="space-y-2"><label class="text-xs font-bold text-secondary uppercase">Pasta Raiz de Logs</label><div class="flex gap-2"><input v-model="settings.last_folder" class="flex-1 px-3 py-2 bg-theme-10 border border-theme rounded-lg text-xs text-primary"><button @click="handleChooseFolder" class="px-3 py-2 bg-accent-10 text-accent text-[10px] rounded-lg">Selecionar</button></div></div>
                    <div class="space-y-2"><div class="flex justify-between items-center"><label class="text-xs font-bold text-secondary uppercase">Tamanho da Fonte</label><span class="text-xs font-bold text-accent">{{ settings.font_size }}px</span></div><input type="range" :min="8" :max="24" v-model.number="settings.font_size" class="slider-range"></div>
                    <div class="space-y-2"><div class="flex justify-between items-center"><label class="text-xs font-bold text-secondary uppercase">Intervalo de Scan</label><span class="text-xs font-bold text-accent">{{ Number(settings.scan_interval).toFixed(1) }}s</span></div><input type="range" :min="0.5" :max="10" step="0.5" v-model.number="settings.scan_interval" class="slider-range"></div>
                  </div>
                  <div class="space-y-6">
                    <div class="grid grid-cols-2 gap-4">
                      <div class="space-y-2"><label class="text-xs font-bold text-secondary uppercase">Aparência</label><select v-model="settings.appearance_mode" class="w-full px-3 py-2 bg-theme-10 border border-theme rounded-lg text-xs"><option value="dark">Escuro</option><option value="light">Claro</option><option value="system">Sistema</option></select></div>
                      <div class="space-y-2"><label class="text-xs font-bold text-secondary uppercase">Gama de Cores</label><select v-model="settings.ui_theme" class="w-full px-3 py-2 bg-theme-10 border border-theme rounded-lg text-xs"><option value="blue">Oceano Azul</option><option value="green">Esmeralda</option></select></div>
                    </div>
                    <div class="space-y-3"><label class="text-xs font-bold text-secondary uppercase">Sistema de Atualização</label><div class="flex items-center justify-between p-3 bg-theme-10 border border-theme rounded-lg"><div><div class="text-[11px] font-bold text-primary">Atualizações Automáticas</div><div class="text-[10px] text-muted">Verificar ao iniciar o sistema</div></div><label class="relative inline-flex items-center cursor-pointer"><input type="checkbox" v-model="settings.auto_update" class="sr-only peer"><div class="w-8 h-4.5 bg-muted/30 rounded-full peer peer-checked:bg-accent after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:after:translate-x-full"></div></label></div><button @click="handleCheckUpdates" :disabled="checkUpdateLoading" class="w-full flex items-center justify-center gap-2 px-4 py-2 bg-theme-10 border border-theme rounded-lg text-[11px] font-bold transition-all"><RefreshCw class="w-3.5 h-3.5" :class="{'animate-spin': checkUpdateLoading}" />{{ checkUpdateLoading ? 'Buscando...' : 'Verificar agora' }}</button></div>
                  </div>
                </div>
                <div class="mt-8 pt-6 border-t border-theme flex flex-col sm:flex-row items-center justify-between gap-4"><button @click="handleSaveSettings" class="px-8 py-2.5 bg-accent text-white font-bold rounded-xl text-xs shadow-lg shadow-accent/20">Salvar Alterações</button><div class="text-[10px] text-muted font-mono flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-accent/30"></span> LogFácil Pro v{{ appVersion }} · MaxInnov © 2026</div></div>
              </div>
            </div>
          </div>
        </transition>
      </section>

      <footer class="h-7 glass-panel mt-3 px-3 flex items-center justify-between text-[9px] text-muted flex-shrink-0">
        <div class="flex gap-3"><span class="flex items-center gap-1"><span class="w-1.5 h-1.5 bg-green-500 rounded-full"></span> Conectado</span><span v-if="activeLogsCount" class="flex items-center gap-1"><span class="w-1.5 h-1.5 bg-purple-500 rounded-full"></span> {{ activeLogsCount }} serviço(s)</span><span v-if="!isFollowing && currentView === 'logs'" class="flex items-center gap-1 font-bold" :style="{ color: 'var(--status-warning)' }"><Pause class="w-2.5 h-2.5" /> LOG PAUSADO</span></div>
        <button @click="showAboutModal = true" class="flex items-center gap-1.5 hover:text-accent font-medium"><Info class="w-3 h-3" /><span>MaxInnov · v{{ appVersion }}</span></button>
      </footer>
    </main>

    <!-- Modal de Atualização -->
    <transition name="vfade">
      <div v-if="showUpdateModal" class="absolute inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/80 backdrop-blur-sm">
        <div class="glass-panel max-w-md w-full p-5 rounded-xl border border-blue-500/30 shadow-2xl">
          <div class="flex items-center justify-between border-b border-white/10 pb-3 mb-4"><h3 class="text-sm font-bold flex items-center gap-2"><Download class="w-4 h-4 text-blue-400" />Atualização Disponível</h3><button v-if="!isUpdating" @click="showUpdateModal = false" class="p-1 hover:bg-white/10 rounded-md text-slate-400"><X class="w-4 h-4" /></button></div>
          <div v-if="updateInfo" class="space-y-4">
            <div class="px-3 py-2 bg-accent-10 border border-accent/20 rounded-lg"><p class="text-xs text-accent">Nova versão encontrada:</p><p class="text-lg font-bold text-primary">LogFácil Pro v{{ updateInfo.version }}</p></div>
            <div><p class="text-[10px] font-bold text-secondary uppercase tracking-wider mb-1.5">Novidades</p><div class="p-3 bg-theme-10 rounded-lg text-xs text-secondary h-28 overflow-y-auto font-mono whitespace-pre-wrap border border-theme">{{ updateInfo.release_notes || 'Sem detalhes fornecidos.' }}</div></div>
            <div v-if="updateError" class="p-2 border border-rose-500/30 bg-rose-500/10 rounded flex items-center gap-2 text-rose-400 text-[10px]"><AlertTriangle class="w-3.5 h-3.5" />{{ updateError }}</div>
            <div v-if="isUpdating" class="space-y-1.5 pt-2"><div class="flex justify-between text-[10px] text-secondary"><span>Baixando...</span><span>{{ updateProgress }}%</span></div><div class="h-1.5 bg-theme-10 rounded-full overflow-hidden border border-theme"><div class="h-full bg-accent transition-all duration-300" :style="{ width: updateProgress + '%' }"></div></div></div>
            <div class="flex gap-3 pt-3"><button v-if="!isUpdating" @click="showUpdateModal = false" class="flex-1 py-2 bg-theme-10 rounded-lg text-xs font-medium">Mais tarde</button><button @click="startUpdateDownload" :disabled="isUpdating" class="flex-1 py-2 bg-blue-600 text-white rounded-lg text-xs font-bold transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg shadow-blue-500/20"><Download v-if="!isUpdating" class="w-3.5 h-3.5" /><RefreshCw v-else class="w-3.5 h-3.5 animate-spin" />{{ isUpdating ? 'Processando...' : 'Instalar Agora' }}</button></div>
          </div>
        </div>
      </div>
    </transition>

    <!-- Modal Sobre (Discreto) -->
    <transition name="vfade">
      <div v-if="showAboutModal" class="absolute inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" @click.self="showAboutModal = false">
        <div class="glass-panel max-w-sm w-full p-5 rounded-xl border border-theme shadow-2xl">
          <div class="flex items-center gap-3 mb-4">
            <img :src="appLogo" class="w-10 h-10 object-contain" alt="Logo" />
            <div>
              <h3 class="text-sm font-bold text-primary">LogFácil Pro</h3>
              <p class="text-[10px] font-mono text-muted">Versão {{ appVersion }}</p>
            </div>
          </div>
          
          <div class="space-y-3 text-[11px] text-secondary leading-relaxed border-t border-theme pt-4">
            <p>Solução desenvolvida pela <span class="text-primary font-medium">MaxInnov</span> com o objetivo de otimizar e acelerar o suporte técnico por meio da análise inteligente de logs.</p>
            
            <div class="bg-theme-10 p-2.5 rounded-lg border border-theme">
              <p class="font-medium text-primary mb-1 flex items-center gap-1.5"><ShieldCheck class="w-3.5 h-3.5 text-green-500" /> Ferramenta Independente</p>
              <p class="text-[10px] text-secondary">O LogFácil atua exclusivamente como ferramenta de consulta local. Não possui coleta externa de dados e não interfere no funcionamento de outros serviços.</p>
            </div>

            <div class="bg-emerald-500/10 border border-emerald-500/20 p-2.5 rounded-lg flex items-center justify-between">
              <div>
                <p class="font-medium text-emerald-400 text-[10px] flex items-center gap-1.5 mb-0.5">
                  <Heart class="w-3 h-3" /> Apoie o Projeto
                </p>
                <p class="text-[9px] text-emerald-300 font-mono select-all">contato@maxinnov.com.br</p>
              </div>
              <span class="px-1.5 py-0.5 bg-emerald-500/20 rounded text-emerald-300 text-[9px] font-bold tracking-widest uppercase">PIX</span>
            </div>
          </div>

          <div class="mt-5 pt-3 border-t border-theme flex items-center justify-between">
            <span class="text-[9px] text-muted font-mono">MIT License © 2026</span>
            <button @click="showAboutModal = false" class="px-3 py-1.5 bg-theme-10 hover:bg-theme-10/80 border border-theme rounded-lg text-[10px] font-medium transition-colors text-primary">
              Fechar
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.vfade-enter-active, .vfade-leave-active { transition: opacity 0.12s ease; }
.vfade-enter-from, .vfade-leave-to { opacity: 0; }
.slide-up-enter-active, .slide-up-leave-active { transition: all 0.15s ease; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(6px); }

.log-exception  { color: #ff6b6b; font-weight: 600; }
.log-warn-strong{ color: #ffba08; font-weight: 600; }
.log-error      { color: #ff6b6b; }
.log-warn       { color: #ffd93d; }
.log-info       { color: #6bc167; }
.log-debug      { color: #868e96; }
.log-default    { color: #8da0b5; }

.hl-search  { background: #FFD700; color: #000; border-radius: 2px; padding: 0 1px; }
.hl-current { background: #FF6B00; color: #fff; border-radius: 2px; padding: 0 1px; font-weight: 600; }
.hl-marker  { background: #4dabf7; color: #fff; border-radius: 2px; padding: 0 1px; }

.minimap-panel {
  width: 30px;
  flex-shrink: 0;
  background: var(--log-terminal-bg);
  border: 1px solid var(--border-muted);
  border-radius: 6px;
  overflow: hidden;
  cursor: crosshair;
  position: relative;
  display: flex;
  flex-direction: column;
}
.minimap-viewport {
  position: absolute; left: 0; right: 0;
  background: var(--card-hover);
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
  pointer-events: none; z-index: 10;
}
.minimap-strip       { width: 100%; opacity: 0.85; }
.minimap-strip-empty { width: 100%; background: transparent; }

.tabs-hide-scroll { 
  scrollbar-width: none; 
  -webkit-mask-image: linear-gradient(to right, transparent, black 20px, black calc(100% - 20px), transparent);
}
.tabs-hide-scroll::-webkit-scrollbar { display: none; }

.slider-range {
  -webkit-appearance: none;
  width: 100%; height: 4px;
  background: var(--border-color); border-radius: 9999px; outline: none; cursor: pointer;
}
.slider-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px; height: 14px; border-radius: 50%;
  background: var(--accent-color); cursor: pointer;
  box-shadow: 0 0 8px var(--accent-10); border: 2px solid white;
}
</style>