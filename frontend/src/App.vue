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
  CheckForUpdates, DownloadAndInstallUpdate 
} from '../wailsjs/go/main/App'
import { EventsOn } from '../wailsjs/runtime/runtime'

// ─── Navegação ─────────────────────────────────────────────────────────────
const currentView = ref('dashboard')
const sidebarCollapsed = ref(false)

// ─── Configurações ─────────────────────────────────────────────────────────
const settings = ref({
  last_folder: '', appearance_mode: 'dark', ui_theme: 'blue',
  auto_update: true, font_size: 13, scan_interval: 2.0, max_view_lines: 1000
})

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

// ─── Export ────────────────────────────────────────────────────────────────
const exportFolders = ref([])
const selectedFolders = ref([])
const exportPeriod = ref('7')
const customDateStart = ref('')
const customDateEnd = ref('')

// ─────────────────────────────────────────────────────────────────────────────
// LOG STATE
// Mesmo modelo do Python: serviceLogs = buffer renderizado, pausedLines = buffer_pausado
// ─────────────────────────────────────────────────────────────────────────────
const serviceLogs = ref({})      // buffer ativo (renderizado)
const pausedLines = ref({})      // buffer durante pausa — idêntico ao paused_buffer do Python
const activeLogTab = ref('')
const logContainerRef = ref(null)
const tabsContainerRef = ref(null) // Ref para scroll horizontal das abas
const isFollowing = ref(true)    // self.follow no Python

// ─── Marcador / Custom Highlight — idêntico ao entry_highlight do Python ───
// cor: #4dabf7 (highlight_color no Python)
const customHighlightTerm = ref('')
const HIGHLIGHT_COLOR = '#4dabf7'   // Python: self.colors["highlight_color"]

// ─── Busca Incremental (Ctrl+F) — idêntico ao IncrementalSearch do Python ─
const showLogSearch = ref(false)
const logSearchQuery = ref('')
const logSearchInputRef = ref(null)
const currentMatchIdx = ref(0)
const caseSensitive = ref(false)

// ─── Minimap — idêntico ao LogMinimap do Python ───────────────────────────
const showMinimap = ref(true)
const minimapRef = ref(null)
const logScrollTop = ref(0)
const logScrollHeight = ref(1)
const logClientHeight = ref(1)

// ─── Computed ──────────────────────────────────────────────────────────────
const activeLogsCount = computed(() => Object.keys(serviceLogs.value).length)

const criticalAlerts = computed(() => {
  let count = 0
  if (!logMarkers.value.length) return 0
  
  // Filtra apenas markers que são considerados erros críticos para o dashboard
  const errorStyles = ['exception', 'error']
  const errorPatterns = logMarkers.value
    .filter(m => errorStyles.includes(m.level))
    .map(m => m.pattern.toUpperCase())

  if (!errorPatterns.length) return 0

  for (const lines of Object.values(serviceLogs.value)) {
    for (const line of lines) {
      const upperLine = line.toUpperCase()
      for (const p of errorPatterns) {
        if (upperLine.includes(p)) {
          count++
          break // Conta apenas uma vez por linha
        }
      }
    }
  }
  return count
})

// Linhas da aba ativa
const currentLines = computed(() =>
  (activeLogTab.value && serviceLogs.value[activeLogTab.value])
    ? serviceLogs.value[activeLogTab.value]
    : []
)

// Conta não-lidas em pausa para o badge (equivale ao self.unread do Python)
const unreadCount = computed(() =>
  (!activeLogTab.value || isFollowing.value) ? 0
    : (pausedLines.value[activeLogTab.value] || []).length
)

// Índices de todas as linhas que contêm o termo de busca
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

// ─── Python minimap colors ─────────────────────────────────────────────────
// Cores sincronizadas com LogMinimap.colors + log_tab.colors + text_markers
// ERROR: #ff4d4d | WARN: #ffa500 | CUSTOM_HL: #3498db | slider: #444
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

// Minimap viewport indicator
const viewportStyle = computed(() => {
  const total = logScrollHeight.value, client = logClientHeight.value
  if (total <= client || total <= 0) return { top: '0%', height: '100%' }
  return {
    top:    ((logScrollTop.value / total)  * 100).toFixed(2) + '%',
    height: (Math.max(client / total, 0.05) * 100).toFixed(2) + '%'
  }
})

// Minimap line height like Python: smaller for more lines
const mmLineH = computed(() => {
  const n = currentLines.value.length
  return n > 800 ? 1 : n > 400 ? 1.5 : 2
})

// ─── Syntax Highlighting — cores idênticas ao Python self.colors / text_markers ─
// ERROR: #ff6b6b | WARN: #ffd93d | INFO: #6bc167 | DEBUG: #868e96
// text_markers: "Retorno: 500" → #ffd93d, "Retorno: 404" → #ffba08, "Exception" → #ff6b6b
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
  return null // Usa a cor padrão do CSS
}

// ─── Highlight parts — Marcador + Busca ───────────────────────────────────
// Retorna lista de partes {text, type} ou null se sem destaques
// Prioridade: busca > marcador (como no Python, último tag_config vence)
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

// Auto-pause ao rolar para cima com mouse wheel — idêntico ao _on_scroll do Python
// Python: if event and self.follow and event.delta > 0: self.toggle_follow()
function handleLogScroll(e) {
  const el = e.target
  logScrollTop.value  = el.scrollTop
  logScrollHeight.value = el.scrollHeight
  logClientHeight.value = el.clientHeight
  // Pausa ao rolar pra cima (scroll-up = saiu do fim)
  if (isFollowing.value && el.scrollTop + el.clientHeight < el.scrollHeight - 50) {
    isFollowing.value = false
  }
}

// ─── Scroll das Abas ──────────────────────────────────────────────────────
// Permite scroll horizontal com a roda do mouse
function handleTabsWheel(e) {
  if (!tabsContainerRef.value) return
  tabsContainerRef.value.scrollLeft += e.deltaY
}

// Centraliza a aba ativa
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

// ─── Flush / Toggle Follow — idêntico ao toggle_follow + _flush_buffer do Python ─
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

// ─── Append lines — idêntico ao _drain + _append do Python ────────────────
function addLines(svc, lines) {
  const max = settings.value.max_view_lines || 1000
  if (!serviceLogs.value[svc]) {
    serviceLogs.value[svc] = []
    if (!activeLogTab.value) activeLogTab.value = svc
  }
  serviceLogs.value[svc].push(...lines)
  if (serviceLogs.value[svc].length > max)
    serviceLogs.value[svc] = serviceLogs.value[svc].slice(-max)
}

// ─── Busca incremental — idêntico ao IncrementalSearch do Python ───────────
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

// ─── Keyboard handler — F2 + Ctrl+F + Escape + Enter/Shift+Enter ──────────
function handleKey(ev) {
  if (currentView.value !== 'logs') return

  if (ev.key === 'F2') {
    ev.preventDefault(); toggleFollow(); return
  }
  if (ev.ctrlKey && ev.key.toLowerCase() === 'f') {
    ev.preventDefault()
    showLogSearch.value = true
    nextTick(() => logSearchInputRef.value?.focus())
    if (isFollowing.value) toggleFollow() // pausa ao abrir busca
    return
  }
  if (ev.key === 'Escape' && showLogSearch.value) {
    showLogSearch.value = false; logSearchQuery.value = ''; return
  }
  if (showLogSearch.value) {
    if (ev.key === 'Enter')     { ev.preventDefault(); ev.shiftKey ? searchPrev() : searchNext() }
    if (ev.key === 'ArrowDown') { ev.preventDefault(); searchNext() }
    if (ev.key === 'ArrowUp')   { ev.preventDefault(); searchPrev() }
  }
}

// ─── Data loading ──────────────────────────────────────────────────────────
async function loadInitialData() {
  const s = await GetSettings(); if (s) settings.value = s
  isAdmin.value = await IsAdmin()
  localIP.value = await GetIP()
  logMarkers.value = await GetLogMarkers()
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

async function refreshServices() {
  components.value = await GetServiceStatuses()
}

async function handleRestartComponent(name) {
  if (!isAdmin.value) { alert('Requer privilégios de Administrador.'); return }
  loading.value = true
  try { 
    const res = await RestartComponent(name)
    
    // Wails v2: se retornar (bool, string), res costuma ser o primeiro valor.
    // Mas se res for true, exibimos a mensagem de sucesso amigável.
    if (res === true) {
      alert(`O serviço '${name}' foi reiniciado com sucesso!`)
    } else if (Array.isArray(res)) {
       // Caso o Wails retorne o array/tuple [bool, string]
       alert(res[1])
    } else {
       // Caso seja uma string de erro ou outro formato
       alert(res || "Operação concluída.")
    }
    
    refreshServices() 
  }
  catch (e) { alert('Erro: ' + e) } finally { loading.value = false }
}

async function loadExportData() {
  exportFolders.value = await GetExportFolders()
}

async function handleExport() {
  if (!selectedFolders.value.length) { alert('Selecione ao menos uma pasta.'); return }
  loading.value = true
  try { 
    const res = await ExportLogs(selectedFolders.value, exportPeriod.value, customDateStart.value, customDateEnd.value)
    const msg = Array.isArray(res) ? res[1] : res
    alert(msg)
  }
  catch (e) { alert('Erro: ' + e) } finally { loading.value = false }
}

async function handleExportPDVsCSV() {
  if (!pdvs.value.length) { alert('Nenhum PDV disponível.'); return }
  loading.value = true
  try { 
    const res = await ExportPDVsCSV(pdvs.value)
    const msg = Array.isArray(res) ? res[1] : res
    alert(msg)
  }
  catch (e) { alert('Erro: ' + e) } finally { loading.value = false }
}

// ─── Settings: save + reload + apply font_size ────────────────────────────
// Idêntico ao update_settings() do Python: reaplica fonte e configurações ao vivo
async function handleSaveSettings() {
  try {
    await SaveSettings(settings.value)
    // Recarrega do backend para confirmar (como o Python faz _load_settings no init)
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
  if (serviceLogs.value[svc]) serviceLogs.value[svc] = []
  if (pausedLines.value[svc]) pausedLines.value[svc] = []
}

// ─── Watch view ────────────────────────────────────────────────────────────
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

// ─── Update Handlers ──────────────────────────────────────────────────────
async function handleCheckUpdates() {
  checkUpdateLoading.value = true
  updateError.value = ''
  try {
    const res = await CheckForUpdates()
    if (res.has_update) {
      updateInfo.value = res
      showUpdateModal.value = true
    } else {
      alert(res.message || 'O sistema já está na última versão.')
    }
  } catch (err) {
    alert('Erro ao buscar atualização: ' + err)
  } finally {
    checkUpdateLoading.value = false
  }
}

async function startUpdateDownload() {
  if (!updateInfo.value || !updateInfo.value.download_url) return
  isUpdating.value = true
  updateError.value = ''
  updateProgress.value = 0
  
  try {
    const res = await DownloadAndInstallUpdate(updateInfo.value.download_url)
    // A função no Go retornará uma mensagem se teve sucesso e irá fechar a aplicação
    console.log(res)
  } catch(err) {
    updateError.value = "Erro no Update: " + err
    isUpdating.value = false
  }
}

// ─── Lifecycle ─────────────────────────────────────────────────────────────
onMounted(() => {
  loadInitialData()
  window.addEventListener('keydown', handleKey)

  // Recebe chunks do backend — idêntico ao _drain do Python:
  // se self.follow → _append direto, senão → paused_buffer
  EventsOn('service-log-append', update => {
    if (!update?.service) return
    const lines = update.content.split('\n').filter(l => l.trim())
    if (!lines.length) return

    if (!isFollowing.value) {
      // Pausa: acumula no pausedLines (Python: paused_buffer.append)
      if (!pausedLines.value[update.service]) pausedLines.value[update.service] = []
      pausedLines.value[update.service].push(...lines)
    } else {
      // Seguindo: adiciona ao buffer renderizado e rola para o fim
      addLines(update.service, lines)
      if (activeLogTab.value === update.service) {
        scrollToBottom()
        nextTick(updateMetrics)
      }
    }
  })

  // Listener para atualização de IP em tempo real (solicitado a cada 60s pelo usuário)
  EventsOn('ip-updated', ip => {
    if (ip) localIP.value = ip
  })

  EventsOn('update-available', res => {
    updateInfo.value = res
    showUpdateModal.value = true
  })

  EventsOn('update-progress', prog => {
    updateProgress.value = prog.percent
    if (prog.total > 1024 * 1024) {
      updateBytesStr.value = `${(prog.downloaded / (1024*1024)).toFixed(1)} / ${(prog.total / (1024*1024)).toFixed(1)} MB`
    } else {
      updateBytesStr.value = `${(prog.downloaded / 1024).toFixed(1)} / ${(prog.total / 1024).toFixed(1)} KB`
    }
  })
})

onUnmounted(() => { window.removeEventListener('keydown', handleKey) })
</script>

<template>
  <div :class="['flex h-screen overflow-hidden transition-colors duration-300', themeClass]" style="font-family: 'Segoe UI', system-ui, sans-serif">

    <!-- ═══ SIDEBAR ═══════════════════════════════════════════════════════ -->
    <aside :class="['glass-panel m-3 flex flex-col flex-shrink-0 transition-all duration-300 ease-in-out overflow-hidden',
                    sidebarCollapsed ? 'w-[52px]' : 'w-56']">
      <!-- Header da sidebar -->
      <div class="flex items-center justify-between p-3 border-b border-white/5 min-h-[52px] relative">
        <div v-if="!sidebarCollapsed" class="flex items-center gap-2">
          <!-- TODO: Cole o seu arquivo logo.png dentro da pasta frontend/src/assets/ -->
          <img src="./assets/logo.png" class="w-6 h-6 object-contain" alt="Logo" />
          <span class="text-sm font-bold whitespace-nowrap">LogFácil <span class="text-blue-400">Pro</span></span>
        </div>
        
        <button @click="sidebarCollapsed = !sidebarCollapsed"
          :class="['p-1.5 rounded hover:bg-white/10 text-slate-500 hover:text-slate-300 transition-all flex-shrink-0',
                   sidebarCollapsed ? 'mx-auto' : '']"
          :title="sidebarCollapsed ? 'Expandir' : 'Recolher'">
          <PanelLeftClose v-if="!sidebarCollapsed" class="w-3.5 h-3.5" />
          <PanelLeftOpen v-else class="w-4 h-4" />
        </button>
      </div>

      <!-- Nav -->
      <nav class="flex-1 p-1.5 space-y-0.5 overflow-hidden">
        <button v-for="item in [
          { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
          { id: 'logs',      icon: FileText,        label: 'Monitor de Logs' },
          { id: 'monitor',   icon: Monitor,         label: 'Serviços PDV' },
          { id: 'export',    icon: Download,        label: 'Exportar' },
        ]" :key="item.id" @click="currentView = item.id"
          :class="['w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-xs',
                   sidebarCollapsed ? 'justify-center' : '',
                   currentView === item.id
                     ? 'bg-blue-500/15 text-blue-400'
                     : 'hover:bg-white/5 text-slate-400 hover:text-slate-200']"
          :title="sidebarCollapsed ? item.label : ''">
          <component :is="item.icon" class="w-4 h-4 flex-shrink-0" />
          <span v-if="!sidebarCollapsed" class="font-medium whitespace-nowrap">{{ item.label }}</span>
        </button>
      </nav>

      <!-- Rodapé -->
      <div class="p-1.5 border-t border-white/5 space-y-1">
        <button @click="currentView = 'settings'"
          :class="['w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs transition-all',
                   sidebarCollapsed ? 'justify-center' : '',
                   currentView === 'settings' ? 'bg-blue-500/15 text-blue-400' : 'hover:bg-white/5 text-slate-400']"
          :title="sidebarCollapsed ? 'Configurações' : ''">
          <Settings class="w-4 h-4 flex-shrink-0" />
          <span v-if="!sidebarCollapsed" class="font-medium">Configurações</span>
        </button>

        <!-- Admin badge -->
        <div v-if="!sidebarCollapsed">
          <div v-if="!isAdmin" class="p-2.5 bg-amber-500/10 border border-amber-500/20 rounded-lg">
            <div class="flex items-center gap-1.5 text-amber-400 mb-1.5 text-[10px] font-bold">
              <ShieldAlert class="w-3 h-3" /> MODO RESTRITO
            </div>
            <button @click="RestartAsAdmin()"
              class="w-full py-1 bg-amber-500 hover:bg-amber-400 text-slate-900 font-bold rounded text-[10px] transition-all">
              Elevar Privilégios
            </button>
          </div>
          <div v-else class="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] text-green-400 bg-green-500/10 border border-green-500/20 rounded-lg">
            <ShieldCheck class="w-3 h-3" /><span class="font-bold">ADMINISTRADOR</span>
          </div>
        </div>
        <div v-else class="flex justify-center py-1">
          <div :class="['w-6 h-6 rounded-md flex items-center justify-center',
                        isAdmin ? 'bg-green-500/10' : 'bg-amber-500/10']"
            :title="isAdmin ? 'Administrador' : 'Modo Restrito'">
            <ShieldCheck v-if="isAdmin" class="w-3.5 h-3.5 text-green-400" />
            <ShieldAlert v-else class="w-3.5 h-3.5 text-amber-400" />
          </div>
        </div>
      </div>
    </aside>

    <!-- ═══ MAIN ══════════════════════════════════════════════════════════ -->
    <main class="flex-1 flex flex-col m-3 ml-0 overflow-hidden min-w-0">

      <!-- Header compacto (sem barra de busca global) -->
      <header class="h-12 glass-panel mb-3 px-4 flex items-center justify-between flex-shrink-0">
        <div class="flex items-center gap-2">
          <ChevronRight class="w-3 h-3 text-slate-500" />
          <h2 class="text-sm font-semibold opacity-90">
            {{ { dashboard:'Dashboard', logs:'Monitor de Logs', monitor:'Serviços PDV', export:'Exportar Logs', settings:'Configurações' }[currentView] }}
          </h2>
          <div v-if="loading" class="animate-spin text-blue-500 ml-1">
            <RefreshCw class="w-3 h-3" />
          </div>
        </div>
        <div class="flex items-center gap-3">
          <!-- Dica F2 — visível apenas na aba de logs -->
          <span v-if="currentView === 'logs'"
            class="hidden sm:flex items-center gap-1 text-[9px] text-slate-600 border border-white/10 px-2 py-1 rounded font-mono">
            F2 Pausar · Ctrl+F Buscar
          </span>
          <span class="text-[9px] text-slate-700 font-mono hidden md:block">v2.1.3-GO</span>
        </div>
      </header>

      <!-- Content -->
      <section :class="['flex-1 glass-panel relative min-h-0',
                        currentView === 'logs' ? 'overflow-hidden flex flex-col p-3' : 'overflow-y-auto p-5']">
        <transition name="vfade" mode="out-in">
          <div :key="currentView" class="h-full flex flex-col">

            <!-- ═══ DASHBOARD ════════════════════════════════════════════ -->
            <div v-if="currentView === 'dashboard'" class="space-y-4">
              <!-- Cards -->
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div class="glass-card p-4">
                  <div class="flex items-start justify-between">
                    <div>
                      <p class="text-[10px] text-slate-400 uppercase tracking-wider font-medium">PDVs em Operação</p>
                      <div class="text-3xl font-bold mt-1.5 tabular-nums">{{ pdvs.length }}</div>
                    </div>
                    <div class="w-9 h-9 bg-blue-500/10 rounded-xl flex items-center justify-center">
                      <Monitor class="w-4.5 h-4.5 text-blue-400" />
                    </div>
                  </div>
                  <div class="mt-3 text-[10px] text-green-400 flex items-center gap-1">
                    <span class="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span> Monitorando
                  </div>
                </div>

                <div class="glass-card p-4">
                  <div class="flex items-start justify-between">
                    <div>
                      <p class="text-[10px] text-slate-400 uppercase tracking-wider font-medium">Alertas Críticos</p>
                      <div :class="['text-3xl font-bold mt-1.5 tabular-nums', criticalAlerts > 0 ? 'text-rose-400' : '']">{{ criticalAlerts }}</div>
                    </div>
                    <div :class="['w-9 h-9 rounded-xl flex items-center justify-center', criticalAlerts > 0 ? 'bg-rose-500/10' : 'bg-white/5']">
                      <AlertTriangle :class="['w-4.5 h-4.5', criticalAlerts > 0 ? 'text-rose-400' : 'text-slate-600']" />
                    </div>
                  </div>
                  <p class="mt-3 text-[10px] text-slate-500">{{ criticalAlerts === 0 ? 'Nenhum erro detectado' : `${criticalAlerts} ocorrência(s)` }}</p>
                </div>

                <div class="glass-card p-4">
                  <div class="flex items-start justify-between">
                    <div>
                      <p class="text-[10px] text-slate-400 uppercase tracking-wider font-medium">Logs Ativos</p>
                      <div class="text-3xl font-bold mt-1.5 tabular-nums">{{ activeLogsCount }}</div>
                    </div>
                    <div class="w-9 h-9 bg-purple-500/10 rounded-xl flex items-center justify-center">
                      <FileText class="w-4.5 h-4.5 text-purple-400" />
                    </div>
                  </div>
                  <div class="mt-3 text-[10px] text-blue-400 flex items-center gap-1">
                    <Wifi class="w-3 h-3" /> API Local {{ localIP }}:8080
                  </div>
                </div>
              </div>

              <!-- Tabela PDVs -->
              <div class="glass-card overflow-hidden">
                <div class="p-3 border-b border-white/10 flex items-center justify-between">
                  <h3 class="font-semibold text-xs">Atividade Recente dos PDVs</h3>
                  <div class="flex items-center gap-4">
                    <button @click="handleExportPDVsCSV" :disabled="!pdvs.length"
                      class="text-[10px] text-slate-400 hover:text-blue-400 flex items-center gap-1 transition-colors disabled:opacity-30">
                      <FileDown class="w-3 h-3" /> Exportar CSV
                    </button>
                    <button @click="refreshDashboard" class="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-1">
                      <RefreshCw class="w-3 h-3" :class="{'animate-spin': loading}" /> Atualizar
                    </button>
                  </div>
                </div>
                <div class="overflow-x-auto">
                  <table class="w-full text-left text-[11px]">
                    <thead class="bg-white/5">
                      <tr>
                        <th class="p-2.5 font-medium text-slate-400">Código</th>
                        <th class="p-2.5 font-medium text-slate-400">ID Interno</th>
                        <th class="p-2.5 font-medium text-slate-400">Nome</th>
                        <th class="p-2.5 font-medium text-slate-400">IP</th>
                        <th class="p-2.5 font-medium text-slate-400">Status</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-white/5">
                      <tr v-for="p in pdvs" :key="p.id_interno" class="hover:bg-white/5 transition-colors">
                        <td class="p-2.5 font-mono text-blue-300">{{ p.codigo }}</td>
                        <td class="p-2.5 text-slate-400">{{ p.id_interno }}</td>
                        <td class="p-2.5">{{ p.nome }}</td>
                        <td class="p-2.5 text-slate-300">{{ p.ip }}</td>
                        <td class="p-2.5">
                          <span class="px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded text-[9px] font-medium">Ativo</span>
                        </td>
                      </tr>
                      <tr v-if="!pdvs.length">
                        <td colspan="5" class="p-6 text-center text-slate-500 italic text-xs">
                          {{ logMsg || 'Nenhum PDV identificado no log recente.' }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <!-- ═══ LOG VIEW (Multi-Aba) ══════════════════════════════════ -->
            <div v-if="currentView === 'logs'" class="h-full flex flex-col overflow-hidden">

              <!-- Toolbar superior: Marcador (Custom Highlight) + minimap toggle -->
              <div class="flex items-center justify-between mb-2 flex-shrink-0 gap-2">
                <!-- Marcador — idêntico ao highlighter_bar do Python -->
                <div class="flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg flex-1 max-w-xs">
                  <Bookmark class="w-3 h-3 text-blue-400 flex-shrink-0" />
                  <span class="text-[9px] text-slate-500 font-bold flex-shrink-0">MARCADOR</span>
                  <input v-model="customHighlightTerm"
                    placeholder="Termo para destacar..."
                    class="bg-transparent text-xs outline-none placeholder:text-slate-600 text-slate-300 flex-1 min-w-0">
                  <button v-if="customHighlightTerm" @click="customHighlightTerm = ''" class="text-slate-600 hover:text-slate-400">
                    <X class="w-3 h-3" />
                  </button>
                </div>

                <div class="flex items-center gap-2 flex-shrink-0">
                  <!-- Toggle minimap -->
                  <button @click="showMinimap = !showMinimap"
                    :class="['px-2 py-1.5 rounded-lg border text-[10px] font-medium flex items-center gap-1 transition-all',
                             showMinimap ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' : 'bg-white/5 border-white/10 text-slate-500']"
                    title="Alternar Minimap (M)">
                    <Map class="w-3 h-3" />
                  </button>
                  <!-- Stream indicator -->
                  <span class="flex items-center gap-1 px-2 py-1 bg-white/5 border border-white/10 text-[9px] font-bold text-slate-400 rounded">
                    <span class="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
                    STREAM
                  </span>
                </div>
              </div>

              <!-- Tabs de serviços -->
              <div ref="tabsContainerRef" 
                @wheel.passive="handleTabsWheel"
                class="flex gap-0.5 mb-1 border-b border-theme flex-shrink-0 pb-px tabs-hide-scroll overflow-x-auto select-none">
                <button v-for="(lines, svc) in serviceLogs" :key="svc"
                  @click="scrollToActiveTab(svc)"
                  :class="['px-3 py-1.5 rounded-t text-[10px] font-bold whitespace-nowrap border-b-2 flex items-center gap-1.5 transition-all flex-shrink-0',
                           activeLogTab === svc
                             ? 'bg-accent-10 text-accent border-accent tab-active'
                             : 'text-secondary border-transparent hover:text-primary hover:bg-theme-10']">
                  <!-- Pulsing dot (like Python status canvas) -->
                  <span class="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    :class="activeLogTab === svc ? 'bg-accent' : 'bg-muted'"></span>
                  {{ svc }}
                  <span class="px-1 bg-theme-10 rounded text-[8px] opacity-60">{{ lines.length }}</span>
                  <!-- Unread badge (like Python self.unread) -->
                  <span v-if="!isFollowing && (pausedLines[svc] || []).length"
                    class="px-1 py-0.5 bg-amber-500/20 text-amber-400 rounded text-[8px] font-bold">
                    +{{ (pausedLines[svc] || []).length }}
                  </span>
                </button>
                <div v-if="!Object.keys(serviceLogs).length" class="py-1.5 text-[10px] text-slate-600 italic flex items-center gap-1.5 px-3">
                  <Activity class="w-3 h-3 animate-pulse" /> Aguardando logs...
                </div>
              </div>

              <!-- Terminal + Minimap -->
              <div class="flex flex-1 min-h-0 gap-2">

                <!-- Log terminal -->
                <div ref="logContainerRef"
                  @scroll="handleLogScroll"
                  class="flex-1 min-w-0 rounded-lg border border-white/5 overflow-y-auto px-3 py-2 shadow-inner log-terminal"
                  :style="{ fontSize: (settings.font_size || 13) + 'px', fontFamily: 'Consolas, monospace', lineHeight: '1.5' }">

                  <template v-if="activeLogTab && serviceLogs[activeLogTab]">
                    <div v-for="(line, idx) in currentLines" :key="idx" :id="`ll-${idx}`"
                      :class="['group flex items-start gap-2 px-1 py-px rounded transition-colors hover:bg-white/5',
                               getLineClass(line),
                               matchedLineIndices[currentMatchIdx] === idx && logSearchQuery ? 'ring-1 ring-blue-500/30' : '']"
                      :style="{ color: getLineColor(line) }">
                      <!-- Número de linha -->
                      <span class="select-none text-[9px] text-slate-700 group-hover:text-slate-500 tabular-nums w-8 text-right flex-shrink-0 pt-px">
                        {{ idx + 1 }}
                      </span>
                      <!-- Conteúdo da linha: sem highlight, com marcador, ou com busca -->
                      <span class="break-all whitespace-pre-wrap flex-1 min-w-0">
                        <template v-if="!logSearchQuery && !customHighlightTerm">{{ line }}</template>
                        <template v-else-if="getLineParts(line, idx)">
                          <template v-for="(part, pi) in getLineParts(line, idx)" :key="pi">
                            <!-- search_highlight: #FFD700 preto — idêntico ao Python IncrementalSearch -->
                            <mark v-if="part.type === 'search'"    class="hl-search">{{ part.text }}</mark>
                            <!-- current_match: #FF6B00 branco — idêntico ao Python current_match tag -->
                            <mark v-else-if="part.type === 'current'" class="hl-current">{{ part.text }}</mark>
                            <!-- CUSTOM_HL: #4dabf7 branco — idêntico ao Python CUSTOM_HL tag -->
                            <mark v-else-if="part.type === 'marker'"   class="hl-marker">{{ part.text }}</mark>
                            <span v-else>{{ part.text }}</span>
                          </template>
                        </template>
                        <template v-else>{{ line }}</template>
                      </span>
                    </div>
                  </template>

                  <div v-else class="h-full flex flex-col items-center justify-center text-slate-700 gap-2">
                    <FileText class="w-8 h-8 opacity-30" />
                    <span class="text-xs">Selecione uma aba para visualizar o log.</span>
                  </div>
                </div>

                <!-- Minimap — idêntico ao LogMinimap do Python (canvas strips) -->
                <div v-if="showMinimap && activeLogTab"
                  ref="minimapRef"
                  @click="handleMinimapClick"
                  class="minimap-panel"
                  title="Clique para navegar">
                  <!-- Viewport indicator (slider no Python) -->
                  <div class="minimap-viewport" :style="viewportStyle"></div>
                  <!-- Strips coloridas por severidade -->
                  <template v-for="(line, idx) in currentLines" :key="idx">
                    <div v-if="getMinimapColor(line)"
                      class="minimap-strip"
                      :style="{ height: mmLineH + 'px', background: getMinimapColor(line) }">
                    </div>
                    <div v-else class="minimap-strip-empty"
                      :style="{ height: mmLineH + 'px' }">
                    </div>
                  </template>
                </div>
              </div>

              <!-- Barra de busca incremental (Ctrl+F) — popup igual ao Python IncrementalSearch -->
              <transition name="slide-up">
                <div v-if="showLogSearch" class="flex items-center gap-2 mt-1.5 flex-shrink-0 px-2 py-1.5 bg-slate-900 border border-blue-500/30 rounded-lg">
                  <Search class="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                  <input ref="logSearchInputRef"
                    v-model="logSearchQuery"
                    @keydown.enter.prevent="searchNext"
                    @keydown.shift.enter.prevent="searchPrev"
                    placeholder="Buscar nos logs... (Enter ↓ · Shift+Enter ↑ · Esc fechar)"
                    class="flex-1 bg-transparent text-xs outline-none text-slate-200 placeholder:text-slate-600">
                  <!-- Contador 1/N — idêntico ao count_label do Python -->
                  <span class="text-[10px] font-mono text-slate-400 flex-shrink-0 w-14 text-right">
                    {{ matchedLineIndices.length > 0 ? `${currentMatchIdx + 1}/${matchedLineIndices.length}` : '0/0' }}
                  </span>
                  <!-- Diferenciar maiúsculas — idêntico ao case_check do Python -->
                  <label class="flex items-center gap-1 text-[9px] text-slate-500 cursor-pointer flex-shrink-0">
                    <input type="checkbox" v-model="caseSensitive" class="w-3 h-3 accent-blue-500"> Aa
                  </label>
                  <!-- ▲ Prev / ▼ Next — idêntico ao btn_prev / btn_next do Python -->
                  <button @click="searchPrev" :disabled="!matchedLineIndices.length" class="p-1 hover:bg-white/10 rounded disabled:opacity-30 transition-all">
                    <ChevronUp class="w-3.5 h-3.5" />
                  </button>
                  <button @click="searchNext" :disabled="!matchedLineIndices.length" class="p-1 hover:bg-white/10 rounded disabled:opacity-30 transition-all">
                    <ChevronDown class="w-3.5 h-3.5" />
                  </button>
                  <!-- Fechar — btn_close vermelho do Python -->
                  <button @click="showLogSearch = false; logSearchQuery = ''"
                    class="p-1 bg-rose-600/20 hover:bg-rose-600/40 text-rose-400 rounded transition-all flex-shrink-0">
                    <X class="w-3.5 h-3.5" />
                  </button>
                </div>
              </transition>

              <!-- Toolbar inferior -->
              <div v-if="activeLogTab" class="flex items-center justify-between mt-1.5 pt-1.5 border-t border-white/5 flex-shrink-0">
                <div class="flex items-center gap-2">
                  <!-- Botão F2 Pausar/Seguir — idêntico ao btn_follow do Python -->
                  <button @click="toggleFollow"
                    :class="['px-3 py-1.5 rounded-lg text-[10px] font-bold flex items-center gap-1.5 transition-all border',
                             isFollowing
                               ? 'bg-blue-600 text-white border-blue-500'
                               : 'bg-amber-500/10 text-amber-400 border-amber-500/20']">
                    <RefreshCw v-if="isFollowing" class="w-3 h-3 animate-spin" />
                    <Pause v-else class="w-3 h-3" />
                    {{ isFollowing ? 'Seguindo — F2' : 'Pausado — F2' }}
                    <!-- Contador de não-lidas (Python: self.unread) -->
                    <span v-if="!isFollowing && unreadCount > 0"
                      class="px-1 py-0.5 bg-amber-500/20 rounded text-[9px]">
                      +{{ unreadCount }}
                    </span>
                  </button>

                  <button @click="handleRestartComponent(activeLogTab)" :disabled="loading || !isAdmin"
                    class="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 rounded-lg text-[10px] flex items-center gap-1.5 transition-all disabled:opacity-40">
                    <RefreshCw class="w-3 h-3" /> Reiniciar
                    <span class="font-mono">{{ activeLogTab }}</span>
                  </button>

                  <!-- Abrir Ctrl+F via botão -->
                  <button @click="showLogSearch = !showLogSearch; if(showLogSearch) nextTick(() => logSearchInputRef?.focus())"
                    :class="['px-3 py-1.5 border rounded-lg text-[10px] flex items-center gap-1.5 transition-all',
                             showLogSearch ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' : 'bg-white/5 border-white/10 text-slate-400']">
                    <Search class="w-3 h-3" /> Ctrl+F
                  </button>
                </div>

                <button @click="clearLogTab(activeLogTab)"
                  class="flex items-center gap-1 text-[10px] text-slate-500 hover:text-rose-400 transition-colors">
                  <Trash2 class="w-3 h-3" /> Limpar
                </button>
              </div>
            </div>

            <!-- ═══ MONITOR DE SERVIÇOS ════════════════════════════════════ -->
            <div v-if="currentView === 'monitor'" class="space-y-4">
              <div class="flex items-center justify-between">
                <p class="text-xs text-slate-500">Atualiza automaticamente a cada 3s.</p>
                <button @click="refreshServices" class="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1.5">
                  <RefreshCw class="w-3 h-3" /> Atualizar
                </button>
              </div>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <div v-for="comp in components" :key="comp.name" class="glass-card p-4 flex flex-col">
                  <div class="flex items-start justify-between mb-3">
                    <div>
                      <h3 class="font-bold text-xs">{{ comp.name }}</h3>
                      <span :class="['mt-1 inline-block px-1.5 py-0.5 rounded text-[9px] font-bold uppercase',
                                     comp.is_ok ? 'bg-green-500/20 text-green-400' : 'bg-rose-500/20 text-rose-400']">
                        {{ comp.status }}
                      </span>
                    </div>
                    <div :class="['w-2 h-2 rounded-full mt-1 flex-shrink-0', comp.is_ok ? 'bg-green-500 animate-pulse' : 'bg-rose-500']"></div>
                  </div>
                  <div class="flex-1 space-y-1 mb-3">
                    <div v-for="svc in (comp.services || [])" :key="svc.name"
                      class="flex items-center justify-between text-[10px] py-0.5 border-b border-white/5 last:border-0">
                      <span class="text-slate-400 font-mono truncate mr-2">{{ svc.name }}</span>
                      <span :class="['font-bold flex-shrink-0 text-[9px]', svc.running ? 'text-green-400' : 'text-rose-400']">
                        {{ svc.running ? 'Running' : 'Stopped' }}
                      </span>
                    </div>
                  </div>
                  <button @click="handleRestartComponent(comp.name)" :disabled="loading || !isAdmin"
                    class="w-full py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[10px] font-bold flex items-center justify-center gap-1.5 transition-all active:scale-95 disabled:opacity-40">
                    <RefreshCw class="w-3 h-3" :class="{'animate-spin': loading}" /> Reiniciar Stack
                  </button>
                </div>
              </div>
            </div>

            <!-- ═══ EXPORT ════════════════════════════════════════════════ -->
            <div v-if="currentView === 'export'" class="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
              <div class="lg:col-span-2 glass-card flex flex-col min-h-0">
                <div class="p-3 border-b border-white/10 flex items-center justify-between flex-shrink-0">
                  <div>
                    <h3 class="font-bold text-xs">Pastas de Logs</h3>
                    <p class="text-[9px] text-slate-500">{{ settings.last_folder || 'C:\\Quality\\LOG' }}</p>
                  </div>
                  <button @click="loadExportData" class="text-[10px] text-blue-400 hover:text-blue-300">Atualizar</button>
                </div>
                <div class="flex-1 overflow-y-auto p-3 space-y-1 min-h-0">
                  <label v-for="folder in exportFolders" :key="folder"
                    class="flex items-center gap-2.5 p-2.5 bg-white/5 rounded-lg cursor-pointer hover:bg-white/10 transition-all group">
                    <input type="checkbox" :value="folder" v-model="selectedFolders" class="w-3.5 h-3.5 accent-blue-500">
                    <span class="text-xs font-mono group-hover:text-blue-300 transition-colors">{{ folder }}</span>
                  </label>
                  <div v-if="!exportFolders.length" class="text-center py-8 text-slate-600 text-xs italic">
                    Nenhuma pasta encontrada.
                  </div>
                </div>
                <div class="p-2.5 border-t border-white/10 flex gap-3 flex-shrink-0">
                  <button @click="selectedFolders = [...exportFolders]" class="text-[10px] text-slate-400 hover:text-blue-400">Selecionar Tudo</button>
                  <span class="text-slate-700">·</span>
                  <button @click="selectedFolders = []" class="text-[10px] text-slate-400 hover:text-rose-400">Limpar</button>
                  <span class="ml-auto text-[10px] text-slate-500">{{ selectedFolders.length }} selecionadas</span>
                </div>
              </div>

              <div class="glass-card p-4 flex flex-col gap-4">
                <div>
                  <h3 class="font-bold text-xs mb-3">Período de Exportação</h3>
                  <div class="space-y-2">
                    <label v-for="p in [{n:'Hoje',v:'0'},{n:'7 dias',v:'7'},{n:'15 dias',v:'15'},{n:'30 dias',v:'30'},{n:'Tudo',v:'all'},{n:'Outro',v:'custom'}]"
                      :key="p.v" class="flex items-center gap-2.5 cursor-pointer group">
                      <input type="radio" name="period" :value="p.v" v-model="exportPeriod" class="w-3.5 h-3.5 accent-blue-500">
                      <span :class="['text-xs', exportPeriod === p.v ? 'text-blue-400 font-medium' : 'text-slate-400']">{{ p.n }}</span>
                    </label>
                  </div>
                </div>
                <div v-if="exportPeriod === 'custom'" class="space-y-2 border-t border-white/10 pt-3">
                  <div><label class="text-[10px] text-slate-400">Início</label>
                    <input v-model="customDateStart" placeholder="DD/MM/AAAA" class="mt-1 w-full px-2.5 py-1.5 bg-white/5 border border-white/10 rounded text-xs focus:outline-none focus:border-blue-500"></div>
                  <div><label class="text-[10px] text-slate-400">Fim</label>
                    <input v-model="customDateEnd" placeholder="DD/MM/AAAA" class="mt-1 w-full px-2.5 py-1.5 bg-white/5 border border-white/10 rounded text-xs focus:outline-none focus:border-blue-500"></div>
                </div>
                <button @click="handleExport" :disabled="loading || !selectedFolders.length"
                  class="mt-auto w-full py-3 bg-green-600 hover:bg-green-500 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 transition-all active:scale-95 disabled:opacity-40">
                  <Download class="w-4 h-4" /> Gerar ZIP
                </button>
              </div>
            </div>

            <!-- ═══ CONFIGURAÇÕES ═════════════════════════════════════════ -->
            <div v-if="currentView === 'settings'" class="max-w-lg mx-auto space-y-4">
              <div class="glass-card p-6">
                <h3 class="text-sm font-bold mb-5 flex items-center gap-2">
                  <Settings class="w-4 h-4 text-blue-500" /> Preferências Gerais
                </h3>
                <div class="space-y-6">
                  <!-- Pasta raiz -->
                  <div class="space-y-1.5">
                    <label class="text-xs font-medium text-slate-300">Pasta Raiz de Logs</label>
                    <div class="flex gap-2">
                      <input v-model="settings.last_folder" placeholder="C:\Quality\LOG"
                        class="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs focus:outline-none focus:border-blue-500 transition-all">
                      <button @click="handleChooseFolder"
                        class="flex items-center gap-1.5 px-3 py-2 bg-blue-600/20 hover:bg-blue-600/40 border border-blue-500/30 text-blue-400 text-[10px] rounded-lg transition-all whitespace-nowrap">
                        <FolderOpen class="w-3 h-3" /> Selecionar
                      </button>
                    </div>
                    <p class="text-[9px] text-slate-600">Padrão: C:\Quality\LOG</p>
                  </div>

                  <!-- Tamanho da fonte — idêntico ao font_slider do Python (range 8-24) -->
                  <!-- Aplicado ao vivo via :style no log container (update_settings equivalente) -->
                  <div class="space-y-1.5">
                    <div class="flex justify-between">
                      <label class="text-xs font-medium text-slate-300">Tamanho da Fonte (Logs)</label>
                      <span class="text-xs font-bold text-blue-400">{{ settings.font_size }}px</span>
                    </div>
                    <input type="range" :min="8" :max="24" :step="1" v-model.number="settings.font_size" class="slider-range">
                    <div class="flex justify-between text-[9px] text-slate-600"><span>8px</span><span>24px</span></div>
                  </div>

                  <!-- Intervalo de scan -->
                  <div class="space-y-1.5">
                    <div class="flex justify-between">
                      <label class="text-xs font-medium text-slate-300">Intervalo de Scan</label>
                      <span class="text-xs font-bold text-blue-400">{{ Number(settings.scan_interval).toFixed(1) }}s</span>
                    </div>
                    <input type="range" :min="0.5" :max="10" :step="0.5" v-model.number="settings.scan_interval" class="slider-range">
                    <div class="flex justify-between text-[9px] text-slate-600"><span>0.5s</span><span>10s</span></div>
                  </div>

                  <!-- Aparência e tema -->
                  <div class="grid grid-cols-2 gap-3">
                    <div class="space-y-1.5">
                      <label class="text-xs font-medium text-slate-300">Aparência</label>
                      <select v-model="settings.appearance_mode" class="w-full px-2.5 py-2 bg-white/5 border border-white/10 rounded-lg text-xs focus:outline-none focus:border-blue-500">
                        <option value="dark">Escuro</option>
                        <option value="light">Claro</option>
                        <option value="system">Sistema</option>
                      </select>
                    </div>
                    <div class="space-y-1.5">
                      <label class="text-xs font-medium text-slate-300">Tema</label>
                      <select v-model="settings.ui_theme" class="w-full px-2.5 py-2 bg-white/5 border border-white/10 rounded-lg text-xs focus:outline-none focus:border-blue-500">
                        <option value="blue">Oceano Azul</option>
                        <option value="green">Esmeralda</option>
                      </select>
                    </div>
                  </div>

                  <!-- Auto-update toggle e check manual -->
                  <div class="flex flex-col gap-2">
                    <div class="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                      <div>
                        <div class="text-xs font-medium">Atualizações Automáticas</div>
                        <div class="text-[9px] text-slate-500 mt-0.5">Verificar lançamento ao iniciar</div>
                      </div>
                      <input type="checkbox" v-model="settings.auto_update" class="w-4 h-4 accent-blue-500">
                    </div>
                    
                    <button @click="handleCheckUpdates" :disabled="checkUpdateLoading"
                      class="w-full flex items-center justify-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs font-medium transition-all disabled:opacity-50 mt-1">
                      <RefreshCw class="w-3.5 h-3.5" :class="{'animate-spin': checkUpdateLoading}" />
                      {{ checkUpdateLoading ? 'Buscando atualizações...' : 'Verificar Atualização Agora' }}
                    </button>
                  </div>
                </div>

                <button @click="handleSaveSettings"
                  class="mt-6 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg text-xs transition-all active:scale-95">
                  Salvar Alterações
                </button>
              </div>
              <div class="text-center text-[9px] text-slate-600">LogFácil Pro v2.1.3-GO · MaxInnov © 2026</div>
            </div>

          </div>
        </transition>
      </section>

      <!-- Status bar -->
      <footer class="h-7 glass-panel mt-3 px-3 flex items-center justify-between text-[9px] text-slate-500 flex-shrink-0">
        <div class="flex gap-3">
          <span class="flex items-center gap-1">
            <span class="w-1.5 h-1.5 bg-green-500 rounded-full"></span> Conectado
          </span>
          <span v-if="activeLogsCount" class="flex items-center gap-1">
            <span class="w-1.5 h-1.5 bg-purple-500 rounded-full"></span>
            {{ activeLogsCount }} serviço(s)
          </span>
          <span v-if="!isFollowing && currentView === 'logs'" class="flex items-center gap-1 text-amber-500">
            <Pause class="w-2.5 h-2.5" /> Log pausado
          </span>
        </div>
        <button @click="showAboutModal = true" class="flex items-center gap-1.5 hover:text-slate-300 transition-colors">
          <Info class="w-3 h-3" />
          <span>MaxInnov · v2.1.3-GO</span>
        </button>
      </footer>
    </main>

    <!-- Modal de Atualização -->
    <transition name="vfade">
      <div v-if="showUpdateModal" class="absolute inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/80 backdrop-blur-sm">
        <div class="glass-panel max-w-md w-full p-5 rounded-xl border border-blue-500/30 shadow-2xl shadow-blue-900/20">
          <div class="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
            <h3 class="text-sm font-bold flex items-center gap-2">
              <Download class="w-4 h-4 text-blue-400" />
              Atualização Disponível
            </h3>
            <button v-if="!isUpdating" @click="showUpdateModal = false" class="p-1 hover:bg-white/10 rounded-md transition-colors text-slate-400 hover:text-white">
              <X class="w-4 h-4" />
            </button>
          </div>

          <div v-if="updateInfo" class="space-y-4">
            <div class="px-3 py-2 bg-blue-500/10 border border-blue-500/20 rounded-lg">
              <p class="text-xs text-blue-300">Nova versão encontrada:</p>
              <p class="text-lg font-bold text-blue-100">LogFácil Pro v{{ updateInfo.version }}</p>
            </div>

            <div>
              <p class="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Novidades</p>
              <div class="p-3 bg-black/30 rounded-lg text-xs text-slate-300 h-28 overflow-y-auto font-mono whitespace-pre-wrap flex-1 min-w-0 break-words shadow-inner border border-white/5 flex flex-col">
                {{ updateInfo.release_notes || 'Sem detalhes fornecidos.' }}
              </div>
            </div>

            <div v-if="updateError" class="p-2 border border-rose-500/30 bg-rose-500/10 rounded flex items-center gap-2 text-rose-400 text-[10px]">
              <AlertTriangle class="w-3.5 h-3.5" />
              {{ updateError }}
            </div>

            <!-- Progresso do Download -->
            <div v-if="isUpdating" class="space-y-1.5 pt-2">
              <div class="flex justify-between text-[10px] text-slate-400 font-medium">
                <span>Baixando atualização...</span>
                <span>{{ updateProgress }}%</span>
              </div>
              <div class="h-1.5 bg-black/40 rounded-full overflow-hidden border border-white/5">
                <div class="h-full bg-blue-500 transition-all duration-300" :style="{ width: updateProgress + '%' }"></div>
              </div>
              <div class="text-[9px] text-center text-slate-500 mt-1" v-if="updateBytesStr">
                {{ updateBytesStr }}
              </div>
            </div>

            <!-- Botões -->
            <div class="flex gap-3 pt-3">
              <button v-if="!isUpdating" @click="showUpdateModal = false"
                class="flex-1 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs font-medium transition-all">
                Mais tarde
              </button>
              <button @click="startUpdateDownload" :disabled="isUpdating"
                class="flex-1 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg shadow-blue-500/20">
                <Download v-if="!isUpdating" class="w-3.5 h-3.5" />
                <RefreshCw v-else class="w-3.5 h-3.5 animate-spin" />
                {{ isUpdating ? 'Processando...' : 'Instalar Agora' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- Modal Sobre (Discreto) -->
    <transition name="vfade">
      <div v-if="showAboutModal" class="absolute inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" @click.self="showAboutModal = false">
        <div class="glass-panel max-w-sm w-full p-5 rounded-xl border border-white/5 shadow-2xl">
          <div class="flex items-center gap-3 mb-4">
            <img src="./assets/logo.png" class="w-10 h-10 object-contain" alt="Logo" />
            <div>
              <h3 class="text-sm font-bold text-slate-200">LogFácil Pro</h3>
              <p class="text-[10px] font-mono text-slate-500">Versão 2.1.3-GO</p>
            </div>
          </div>
          
          <div class="space-y-3 text-[11px] text-slate-400 leading-relaxed border-t border-white/5 pt-4">
            <p>Solução desenvolvida pela <span class="text-slate-300 font-medium">MaxInnov</span> com o objetivo de otimizar e acelerar o suporte técnico por meio da análise inteligente de logs.</p>
            
            <div class="bg-black/20 p-2.5 rounded-lg border border-white/5">
              <p class="font-medium text-slate-300 mb-1 flex items-center gap-1.5"><ShieldCheck class="w-3.5 h-3.5 text-green-500" /> Ferramenta Independente</p>
              <p class="text-[10px]">O LogFácil atua exclusivamente como ferramenta de consulta local. Não possui coleta externa de dados e não interfere no funcionamento de outros serviços.</p>
            </div>

            <div class="bg-emerald-500/10 border border-emerald-500/20 p-2.5 rounded-lg flex items-center justify-between">
              <div>
                <p class="font-medium text-emerald-400 text-[10px] flex items-center gap-1.5 mb-0.5">
                  <Heart class="w-3 h-3" /> Apoie o Projeto
                </p>
                <p class="text-[9px] text-emerald-200/70 font-mono select-all">contato@maxinnov.com.br</p>
              </div>
              <span class="px-1.5 py-0.5 bg-emerald-500/20 rounded text-emerald-300 text-[9px] font-bold tracking-widest">PIX</span>
            </div>
          </div>

          <div class="mt-5 pt-3 border-t border-white/5 flex items-center justify-between">
            <span class="text-[9px] text-slate-600 font-mono">MIT License © 2026</span>
            <button @click="showAboutModal = false" class="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-[10px] font-medium transition-colors text-slate-300">
              Fechar
            </button>
          </div>
        </div>
      </div>
    </transition>

  </div>
</template>

<style scoped>
/* ── Transições ───────────────────────────────────────── */
.vfade-enter-active, .vfade-leave-active { transition: opacity 0.12s ease; }
.vfade-enter-from, .vfade-leave-to { opacity: 0; }
.slide-up-enter-active, .slide-up-leave-active { transition: all 0.15s ease; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(6px); }

/* ── Log level colors — idêntico ao Python self.colors ── */
/* ERROR: #ff6b6b | WARN: #ffd93d | INFO: #6bc167 | DEBUG: #868e96 */
.log-exception  { color: #ff6b6b; font-weight: 600; }
.log-warn-strong{ color: #ffba08; font-weight: 600; }
.log-error      { color: #ff6b6b; }
.log-warn       { color: #ffd93d; }
.log-info       { color: #6bc167; }
.log-debug      { color: #868e96; }
.log-default    { color: #8da0b5; }

/* ── Highlight marks — cores do Python IncrementalSearch ─ */
/* search_highlight: background=#FFD700 fg=#000000 → amarelo ouro */
.hl-search  { background: #FFD700; color: #000; border-radius: 2px; padding: 0 1px; }
/* current_match: background=#FF6B00 fg=#fff → laranja atual */
.hl-current { background: #FF6B00; color: #fff; border-radius: 2px; padding: 0 1px; font-weight: 600; }
/* CUSTOM_HL: background=#4dabf7 fg=#fff → azul profissional suave */
.hl-marker  { background: #4dabf7; color: #fff; border-radius: 2px; padding: 0 1px; }

/* ── Minimap — idêntico ao LogMinimap.py (canvas strips) ─ */
.minimap-panel {
  width: 30px;
  flex-shrink: 0;
  background: #111827;
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 6px;
  overflow: hidden;
  cursor: crosshair;
  position: relative;
  display: flex;
  flex-direction: column;
  user-select: none;
}
/* Viewport indicator = slider do Python */
.minimap-viewport {
  position: absolute; left: 0; right: 0;
  background: rgba(255,255,255,0.08);
  border-top: 1px solid rgba(255,255,255,0.15);
  border-bottom: 1px solid rgba(255,255,255,0.15);
  pointer-events: none; z-index: 10;
  transition: top 0.08s, height 0.08s;
}
/* Strips coloridas — _draw_tag_marks() do Python */
.minimap-strip       { width: 100%; opacity: 0.85; }
.minimap-strip-empty { width: 100%; background: transparent; }

/* ── Tabs scroll oculto + Mask Fade ──────────────────── */
.tabs-hide-scroll { 
  scrollbar-width: none; 
  -webkit-mask-image: linear-gradient(to right, transparent, black 20px, black calc(100% - 20px), transparent);
  mask-image: linear-gradient(to right, transparent, black 20px, black calc(100% - 20px), transparent);
  padding: 0 10px; /* Compensa o fade nas bordas */
}
.tabs-hide-scroll::-webkit-scrollbar { display: none; }

/* ── Range slider ─────────────────────────────────────── */
.slider-range {
  -webkit-appearance: none;
  width: 100%; height: 4px;
  background: rgba(255,255,255,0.1); border-radius: 9999px; outline: none; cursor: pointer;
}
.slider-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 13px; height: 13px; border-radius: 50%;
  background: #3b82f6; cursor: pointer;
  box-shadow: 0 0 5px rgba(59,130,246,0.4);
}
</style>
