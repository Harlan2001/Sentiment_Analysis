import React from 'react'

interface UploadAreaProps {
  onClick: () => void
}

export default function UploadArea({ onClick }: UploadAreaProps) {
  return (
    <div
      onClick={onClick}
      className="group cursor-pointer rounded-xl border-2 border-dashed border-gray-600
                 bg-gray-800/40 hover:border-blue-500/60 hover:bg-gray-800/70
                 transition-all duration-200"
    >
      <div className="flex flex-col items-center justify-center py-8 px-4">
        {/* 上传图标 */}
        <div
          className="w-14 h-14 rounded-full bg-blue-500/10 border border-blue-500/20
                        flex items-center justify-center mb-3
                        group-hover:bg-blue-500/20 group-hover:border-blue-500/40
                        transition-colors duration-200"
        >
          <svg
            className="w-7 h-7 text-blue-400 group-hover:text-blue-300 transition-colors"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
        </div>

        {/* 标题 */}
        <h3 className="text-sm font-medium text-gray-300 group-hover:text-white transition-colors mb-1">
          上传研报 PDF
        </h3>

        {/* 说明 */}
        <p className="text-xs text-gray-500 text-center max-w-sm">
          支持 PDF 格式，上传后将自动解析并提取各项关键信息，之后可一键触发 AI 分析
        </p>

        {/* 底部提示 */}
        <div className="mt-3 flex items-center gap-1.5 text-[10px] text-gray-600">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          仅支持 PDF 格式的研报文件
        </div>
      </div>
    </div>
  )
}
