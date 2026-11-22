import type { Context } from '@deepseek-ai/cordis'
import { existsSync, mkdirSync, copyFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { homedir } from 'node:os'
import { packageRoot, startEditorServer } from './service.ts'
import { pptExportTool, pptServeTool } from './tools.ts'

const SECTION_ORDER = 205

export const inject = ['systemPrompt']

export const NP_PPT_GUIDANCE = `本机已安装 dsh-np-ppt 插件（DSH 原生 PPT 演示文稿专家）：内置 PPTD DSL 引擎、55173 所见即所得可视化编辑器与 Python-PPTX 高保真离线编译内核。能力：1. 标准 9 大视觉风格主题（商务管理、深浅代码、高能增长、炫光紫绿、冷白调研、轻拟态、黑金实验、色谱图表、深蓝杂志）；2. 自动生成 deck/deck.pptd 与 modular 页面并提供淡入淡出切换；3. 55173 本地可视化实时编辑并支持在右上角「导出」弹窗中一键下载高保真 PPTX（集成 RichTextHTMLParser，全面兼容嵌套标签与 rgb 颜色，零样式丢失）；4. 执行 py -3 compiler/export_pptx.py 离线快速编译。用户提到「做PPT / 演示文稿 / 幻灯片 / PPTD / 55173」时即指本插件，请据此协作。`

export interface Config {
  announceToAgent?: boolean
  enabled?: boolean
  port?: number
  autoStartServer?: boolean
}

function ensurePresetInstalled(): void {
  try {
    const userPresetDir = resolve(homedir(), '.dsh', '.agent-presets', 'np-ppt')
    if (!existsSync(userPresetDir)) {
      mkdirSync(userPresetDir, { recursive: true })
    }
    const pluginPresets = resolve(packageRoot, 'presets')
    const presetYml = resolve(pluginPresets, 'preset.yml')
    const agentYml = resolve(pluginPresets, 'agent.cordis.yml')

    if (existsSync(presetYml)) {
      copyFileSync(presetYml, resolve(userPresetDir, 'preset.yml'))
    }
    if (existsSync(agentYml)) {
      copyFileSync(agentYml, resolve(userPresetDir, 'agent.cordis.yml'))
    }
  } catch {}
}

export function apply(ctx: Context, config: Config = {}): void {
  if (config.enabled === false) return

  ensurePresetInstalled()

  if (config.announceToAgent !== false) {
    ctx.effect?.(() => {
      return (ctx as any).systemPrompt?.section?.({
        name: 'plugin:dsh-np-ppt',
        order: SECTION_ORDER,
        text: NP_PPT_GUIDANCE,
      })
    }, 'dsh-np-ppt: system prompt announcement')
  }

  if (config.autoStartServer) {
    startEditorServer({ port: config.port || 55173 }).catch(() => {})
  }
}

export { pptExportTool, pptServeTool }
export * from './service.ts'
