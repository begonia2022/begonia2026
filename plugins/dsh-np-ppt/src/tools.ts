import { runExportPptx, startEditorServer, compilerScriptPath } from './service.ts'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

export interface PptExportParams {
  manifestPath: string
  outputPath?: string
  transition?: 'fade' | 'none'
  force?: boolean
}

export async function pptExportTool(params: PptExportParams): Promise<{ success: boolean; message: string; output?: string }> {
  try {
    const manifest = resolve(process.cwd(), params.manifestPath)
    if (!existsSync(manifest)) {
      return { success: false, message: `PPTD 清单文件未找到: ${manifest}` }
    }
    const result = await runExportPptx(manifest, params.outputPath, params.transition || 'fade', params.force !== false)
    return { success: true, message: 'PPTX 导出成功', output: result.output }
  } catch (error: any) {
    return { success: false, message: `PPTX 导出失败: ${error.message}` }
  }
}

export interface PptServeParams {
  port?: number
  action?: 'start' | 'status'
}

let activeServer: any = null
let activeServerUrl: string | null = null

export async function pptServeTool(params: PptServeParams = {}): Promise<{ running: boolean; url?: string; message: string }> {
  const port = params.port || 55173
  if (params.action === 'status' && activeServer) {
    return { running: true, url: activeServerUrl || `http://127.0.0.1:${port}/`, message: `服务正在运行: ${activeServerUrl}` }
  }

  if (activeServer) {
    return { running: true, url: activeServerUrl || `http://127.0.0.1:${port}/`, message: `服务已在运行中: ${activeServerUrl}` }
  }

  try {
    const { server, url } = await startEditorServer({ port })
    activeServer = server
    activeServerUrl = url
    return { running: true, url, message: `PPT 可视化编辑器已成功启动: ${url}` }
  } catch (error: any) {
    if (error?.code === 'EADDRINUSE') {
      return { running: true, url: `http://127.0.0.1:${port}/`, message: `端口 ${port} 已在运行编辑器服务` }
    }
    return { running: false, message: `启动服务失败: ${error.message}` }
  }
}
