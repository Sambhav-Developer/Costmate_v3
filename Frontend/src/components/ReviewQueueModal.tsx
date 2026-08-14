import React, { useState } from 'react';

interface ReviewQueueItem {
  type: string;
  mark?: string;
  crop_path?: string;
  context: any;
}

interface ReviewQueueModalProps {
  queue: ReviewQueueItem[];
  onSubmit: (resolvedItems: any) => void;
}

export default function ReviewQueueModal({ queue, onSubmit }: ReviewQueueModalProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [resolutions, setResolutions] = useState<any>({});

  const currentItem = queue[currentIndex];

  const handleResolve = (newValue: string) => {
    const updatedResolutions = { ...resolutions, [currentIndex]: newValue };
    setResolutions(updatedResolutions);
    
    if (currentIndex < queue.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      // Done, submit the full resolution object
      onSubmit(updatedResolutions);
    }
  };

  if (!currentItem) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70 backdrop-blur-sm">
      <div className="bg-[#1e1e1e] border border-[#333] rounded-xl shadow-2xl w-full max-w-4xl p-6 flex flex-col h-[80vh]">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-white">Human Review Queue</h2>
          <span className="text-gray-400 bg-gray-800 px-3 py-1 rounded-full text-sm font-medium">
            {currentIndex + 1} / {queue.length}
          </span>
        </div>

        <div className="flex flex-1 gap-6 min-h-0">
          {/* Left: Image or Context */}
          <div className="flex-1 bg-black rounded-lg border border-[#333] flex flex-col items-center justify-center p-4 overflow-hidden relative">
            <span className="absolute top-3 left-3 text-xs font-mono text-gray-500 uppercase tracking-wider">Source Context</span>
            {currentItem.crop_path ? (
              <img 
                src={currentItem.crop_path} 
                alt="Tag Crop" 
                className="max-w-full max-h-full object-contain"
              />
            ) : (
              <div className="text-left w-full h-full overflow-y-auto pt-8 pb-4 px-2">
                <p className="text-gray-400 mb-2 font-medium">Data Context:</p>
                <pre className="font-mono text-xs text-blue-300 whitespace-pre-wrap break-all bg-[#111] p-3 rounded border border-[#222]" style={{ userSelect: 'text', WebkitUserSelect: 'text' }}>
                  {JSON.stringify(currentItem.context, null, 2)}
                </pre>
              </div>
            )}
          </div>

          {/* Right: Input */}
          <div className="flex-1 flex flex-col justify-center bg-[#252525] rounded-lg border border-[#333] p-8 relative">
            <div className="absolute top-4 right-4 flex items-center justify-center w-10 h-10 rounded-full bg-red-500/10 text-red-500">
               <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
               </svg>
            </div>
            
            <h3 className="text-xl font-bold text-white mb-3">
              {currentItem.type === 'ocr_mismatch' && 'OCR Consensus Failed'}
              {currentItem.type === 'schedule_mismatch' && 'Schedule Dual-Read Failed'}
              {currentItem.type === 'orphan_plan_mark' && 'Orphaned Tag Found'}
            </h3>
            
            <p className="text-gray-400 mb-8 leading-relaxed">
              {currentItem.type === 'ocr_mismatch' && 'The AI OCR agents could not agree on the text in this image crop. Please transcribe the exact tag/mark shown.'}
              {currentItem.type === 'schedule_mismatch' && `The mark '${currentItem.mark}' failed the schedule dual-read check. Please type the correct value based on the context.`}
              {currentItem.type === 'orphan_plan_mark' && `The tag '${currentItem.mark}' was found on the plan but not in the schedule. Please provide the correct schedule match or type "IGNORE".`}
            </p>

            <form onSubmit={(e) => {
              e.preventDefault();
              const formData = new FormData(e.currentTarget);
              handleResolve(formData.get('resolution') as string);
              e.currentTarget.reset();
            }}>
              <label className="block text-sm font-medium text-gray-400 mb-2">Resolution / Correct MARK</label>
              <input
                name="resolution"
                type="text"
                required
                autoFocus
                placeholder="Type correct value here..."
                className="w-full bg-black border border-[#444] rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 mb-6 text-lg shadow-inner"
              />
              <button 
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-lg transition-colors shadow-lg"
              >
                Confirm & Next
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
