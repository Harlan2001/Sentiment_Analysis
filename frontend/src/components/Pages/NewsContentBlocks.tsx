import React from 'react'
import type { NewsContentBlock } from '@/types'

interface NewsContentBlocksProps {
  blocks: NewsContentBlock[]
}

const NewsContentBlocks: React.FC<NewsContentBlocksProps> = ({ blocks }) => {
  // 按 block_order 排序
  const sortedBlocks = [...blocks].sort((a, b) => a.block_order - b.block_order)

  const renderTextBlock = (block: NewsContentBlock) => (
    <div key={block.id} className="mb-4">
      <p className="text-gray-300 leading-relaxed whitespace-pre-wrap">{block.content}</p>
    </div>
  )

  const renderQuoteBlock = (block: NewsContentBlock) => (
    <div key={block.id} className="mb-4">
      <blockquote className="border-l-4 border-gray-600 pl-4 italic text-gray-400">{block.content}</blockquote>
    </div>
  )

  const renderImageBlock = (block: NewsContentBlock) => (
    <div key={block.id} className="mb-4">
      {block.image_url && (
        <figure className="text-center">
          <img
            src={block.image_url}
            alt={block.image_alt || '新闻图片'}
            className="max-w-full h-auto rounded-lg mx-auto"
            style={block.image_width ? { width: block.image_width } : {}}
          />
          {block.image_alt && <figcaption className="text-sm text-gray-500 mt-2">{block.image_alt}</figcaption>}
        </figure>
      )}
    </div>
  )

  const renderHeadingBlock = (block: NewsContentBlock) => {
    const HeadingTag = block.heading_level || 'h2'
    const headingClasses = {
      h1: 'text-3xl font-bold text-white mt-6 mb-4',
      h2: 'text-2xl font-semibold text-white mt-5 mb-3',
      h3: 'text-xl font-medium text-white mt-4 mb-2',
      h4: 'text-lg font-medium text-gray-200 mt-3 mb-2',
      h5: 'text-base font-medium text-gray-300 mt-2 mb-1',
      h6: 'text-sm font-medium text-gray-400 mt-2 mb-1',
    }

    return (
      <HeadingTag key={block.id} className={headingClasses[block.heading_level || 'h2']}>
        {block.content}
      </HeadingTag>
    )
  }

  const renderTableBlock = (block: NewsContentBlock) => (
    <div key={block.id} className="mb-4">
      {block.table_caption && (
        <p className="text-sm text-gray-400 mb-2">
          {block.table_caption}
          {block.table_unit && <span className="text-gray-500"> ({block.table_unit})</span>}
        </p>
      )}

      {block.table_headers && block.table_rows && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {block.table_headers.map((header, index) => (
                  <th
                    key={index}
                    className="bg-gray-800 border border-gray-700 px-4 py-2 text-left text-sm font-medium text-gray-300"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.table_rows.map((row, rowIndex) => (
                <tr key={rowIndex} className="hover:bg-gray-800/50">
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="border border-gray-700 px-4 py-2 text-sm text-gray-400">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )

  const renderBlock = (block: NewsContentBlock) => {
    switch (block.block_type) {
      case 'text':
        return renderTextBlock(block)
      case 'quote':
        return renderQuoteBlock(block)
      case 'image':
        return renderImageBlock(block)
      case 'heading':
        return renderHeadingBlock(block)
      case 'table':
        return renderTableBlock(block)
      default:
        return null
    }
  }

  return <div className="space-y-2">{sortedBlocks.map(renderBlock)}</div>
}

export default NewsContentBlocks
