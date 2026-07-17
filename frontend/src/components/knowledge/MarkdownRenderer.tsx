import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check } from 'lucide-react';
import { useState } from 'react';

interface Props {
  content: string;
  className?: string;
}

export default function MarkdownRenderer({ content, className = '' }: Props) {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Code block with copy button
          pre: ({ children, ...props }: any) => {
            const code = typeof children === 'string' ? children
              : children?.props?.children || '';
            return <CodeBlock code={String(code)} {...props} />;
          },
          // Inline code
          code: ({ children, className: cls, ...props }: any) => {
            const isInline = !cls;
            if (isInline) {
              return <code className="inline-code" {...props}>{children}</code>;
            }
            return <code className={cls} {...props}>{children}</code>;
          },
          // Styled links
          a: ({ href, children }: any) => (
            <a href={href} target="_blank" rel="noopener noreferrer"
               className="text-primary-400 hover:text-primary-300 underline decoration-primary-600/50 hover:decoration-primary-400 transition-all">
              {children}
            </a>
          ),
          // Styled tables
          table: ({ children }: any) => (
            <div className="overflow-x-auto my-4 rounded-lg border border-gray-800">
              <table className="min-w-full">{children}</table>
            </div>
          ),
          th: ({ children }: any) => (
            <th className="bg-gray-800/80 px-4 py-2.5 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider border-b border-gray-700">
              {children}
            </th>
          ),
          td: ({ children }: any) => (
            <td className="px-4 py-2 text-sm text-gray-400 border-b border-gray-800/50">{children}</td>
          ),
          // Blockquote
          blockquote: ({ children }: any) => (
            <blockquote className="border-l-3 border-primary-500/60 pl-4 italic text-gray-400 my-4 py-1 bg-primary-600/5 rounded-r-lg">
              {children}
            </blockquote>
          ),
          // Images
          img: ({ src, alt }: any) => (
            <img src={src} alt={alt} className="max-w-full rounded-lg my-3 border border-gray-800"
                 loading="lazy" />
          ),
          // Headings with anchor
          h1: ({ children }: any) => (
            <h1 className="text-2xl font-bold text-white mt-8 mb-4 pb-2 border-b border-gray-800">{children}</h1>
          ),
          h2: ({ children }: any) => (
            <h2 className="text-xl font-semibold text-gray-100 mt-6 mb-3">{children}</h2>
          ),
          h3: ({ children }: any) => (
            <h3 className="text-lg font-medium text-gray-200 mt-5 mb-2">{children}</h3>
          ),
          // Lists
          ul: ({ children }: any) => (
            <ul className="list-disc list-outside ml-5 mb-4 space-y-1 text-gray-300">{children}</ul>
          ),
          ol: ({ children }: any) => (
            <ol className="list-decimal list-outside ml-5 mb-4 space-y-1 text-gray-300">{children}</ol>
          ),
          li: ({ children }: any) => (
            <li className="pl-1 leading-relaxed">{children}</li>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

// Code block with syntax highlight placeholder and copy
function CodeBlock({ code, ...props }: { code: string; [key: string]: any }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-4 rounded-xl overflow-hidden border border-gray-800 bg-gray-900/80">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800/50 border-b border-gray-800">
        <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">code</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 transition-colors"
        >
          {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
          {copied ? '已复制' : '复制'}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-sm leading-relaxed" {...props}>
        <code className="text-gray-300 font-mono text-[13px]">{code}</code>
      </pre>
    </div>
  );
}
