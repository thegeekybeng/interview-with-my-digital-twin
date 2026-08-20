import React, { useEffect, useRef, useState } from 'react';
import { Download } from 'lucide-react';

interface MermaidBlockProps {
  chart: string;
}

export const MermaidBlock: React.FC<MermaidBlockProps> = ({ chart }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>('');
  const [renderError, setRenderError] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    const renderChart = async () => {
      try {
        const uniqueId = `mermaid-${Math.random().toString(36).substring(2, 9)}`;
        
        // Dynamically import the heavy mermaid engine
        const mermaidModule = await import('mermaid');
        const mermaid = mermaidModule.default;
        
        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          securityLevel: 'loose',
          fontFamily: 'Inter, sans-serif',
        });
        
        const { svg } = await mermaid.render(uniqueId, chart);
        if (isMounted) {
          setSvgContent(svg);
          setRenderError(false);
        }
      } catch (err) {
        if (isMounted) setRenderError(true);
      }
    };

    if (chart.trim()) {
      renderChart();
    }

    return () => {
      isMounted = false;
    };
  }, [chart]);

  const handleDownload = () => {
    if (!svgContent) return;
    const blob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `architecture-diagram-${Date.now()}.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (renderError) {
    return <pre className="p-3 bg-red-950/30 text-red-300 rounded font-mono text-xs">{chart}</pre>;
  }

  return (
    <div className="my-3 p-4 bg-slate-900 border border-slate-800 rounded-lg flex flex-col items-center gap-2 overflow-x-auto relative group">
      <div 
        ref={containerRef} 
        className="w-full flex justify-center overflow-x-auto"
        dangerouslySetInnerHTML={{ __html: svgContent }} 
      />
      {svgContent && (
        <button 
          type="button" 
          onClick={handleDownload}
          className="absolute top-2 right-2 p-1.5 bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 hover:text-white rounded border border-slate-700 transition-colors opacity-0 group-hover:opacity-100 flex items-center gap-1.5 text-[10px] font-semibold"
          title="Download Diagram SVG"
        >
          <Download className="w-3.5 h-3.5" />
          Export SVG
        </button>
      )}
    </div>
  );
};
