import React from 'react'
import ReactMarkdown from 'react-markdown'

interface MarkdownContentProps {
  content: string
}

export const MarkdownContent: React.FC<MarkdownContentProps> = ({ content }) => {
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p className="mb-2 leading-relaxed text-gray-700">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-2">{children}</ol>,
        li: ({ children }) => <li className="text-gray-700">{children}</li>,
        h1: ({ children }) => <h1 className="text-lg font-bold mb-2 text-gray-900">{children}</h1>,
        h2: ({ children }) => <h2 className="text-base font-bold mb-2 text-gray-900">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold mb-1 text-gray-900">{children}</h3>,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
