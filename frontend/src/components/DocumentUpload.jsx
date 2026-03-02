/**
 * 文档上传和管理组件
 * 功能：
 * 1. 支持拖拽和点击上传 PDF 文件
 * 2. 显示文档处理进度（解析 → OCR → 合并 → 清理）
 * 3. 预览文档内容（原始 PDF、解析结果、OCR 详情、合并内容、清理结果）
 * 4. 下载各阶段处理结果
 */
import React, { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle, XCircle, Loader2, Trash2, Eye, Download } from 'lucide-react';
import { Button } from './ui/button';
import { documentsApi } from '../api';

/**
 * 预览模态框组件
 * 显示文档的多个处理阶段内容
 * @param {Object} doc - 文档对象
 * @param {string} initialTab - 初始显示的标签页（pdf/parsing/ocr/merging/cleaning）
 * @param {Function} onClose - 关闭回调
 */
const PreviewModal = ({ doc, initialTab = 'pdf', onClose }) => {
    // 最终清理后的内容
    const [content, setContent] = useState(null);
    // 原始合并内容（Markdown + OCR）
    const [rawContent, setRawContent] = useState(null);
    // 纯解析内容（仅 Markdown）
    const [parsingContent, setParsingContent] = useState(null);
    // OCR 识别数据（图片和文本对应关系）
    const [ocrData, setOcrData] = useState([]);
    // 加载状态
    const [loading, setLoading] = useState(false);
    // 文档详情（包含状态信息）
    const [docDetails, setDocDetails] = useState(doc);
    // 当前激活的标签页
    const [tab, setTab] = useState(initialTab);

    /**
     * 下载文件到本地
     * @param {string|Object} data - 文件内容
     * @param {string} filename - 文件名
     * @param {string} type - MIME 类型
     */
    const downloadFile = (data, filename, type = 'text/markdown') => {
        if (!data) return;
        const blob = new Blob([typeof data === 'object' ? JSON.stringify(data, null, 2) : data], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    // 切换标签页时加载内容（PDF 标签页除外）
    React.useEffect(() => {
        if (tab !== 'pdf' && !content) {
        setLoading(true);
        documentsApi.getContent(doc.id)
            .then(res => {
                setContent(res.data.text_content);
                setRawContent(res.data.raw_text_content);
                setParsingContent(res.data.parsing_content);
                setDocDetails(res.data);
                // 解析 OCR 数据（JSON 格式）
                if (res.data.ocr_data) {
                    try {
                        setOcrData(JSON.parse(res.data.ocr_data));
                    } catch(e) {
                        console.error("Failed to parse OCR data", e);
                    }
                }
            })
            .catch(err => setContent("Failed to load content"))
            .finally(() => setLoading(false));
        }
    }, [tab, doc.id]);

    /**
     * 根据当前标签页渲染对应内容
     */
    const renderContent = () => {
        // PDF 预览标签页
        if (tab === 'pdf') {
            return (
                <iframe
                    src={documentsApi.getFileUrl(doc.id)}
                    className="w-full h-full border rounded bg-white"
                    title="PDF Preview"
                />
            );
        }

        if (loading) return <div className="p-4">Loading...</div>;

        // OCR 详情标签页（图片和识别文本对照）
        if (tab === 'ocr') {
            if (!ocrData || ocrData.length === 0) {
                return <div className="p-4 text-gray-500">No OCR data available (maybe no images found).</div>;
            }
            return (
                <div className="w-full h-full overflow-auto bg-white border rounded">
                    {/* 表头 */}
                    <div className="flex justify-between items-center p-2 border-b bg-gray-50 sticky top-0 z-10">
                        <div className="grid grid-cols-2 gap-4 w-full font-medium">
                            <div>Image Source</div>
                            <div>OCR Result (with ID)</div>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => downloadFile(ocrData, `${doc.filename}_ocr.json`, 'application/json')}
                            className="absolute right-2"
                        >
                            <Download className="h-4 w-4" />
                        </Button>
                    </div>
                    {/* OCR 结果列表（图片 + 文本） */}
                    {ocrData.map((item, idx) => (
                        <div key={idx} className="grid grid-cols-2 gap-4 p-4 border-b hover:bg-gray-50">
                            {/* 左侧：图片预览 */}
                            <div className="flex flex-col items-center bg-gray-100 rounded p-2">
                                <img
                                    src={documentsApi.getImageUrl(doc.id, item.image_name)}
                                    alt={`Page ${idx}`}
                                    className="max-w-full max-h-[300px] object-contain cursor-zoom-in mb-2"
                                    onClick={() => window.open(documentsApi.getImageUrl(doc.id, item.image_name), '_blank')}
                                />
                                <span className="text-xs font-mono bg-gray-200 px-2 py-1 rounded text-gray-600 select-all">
                                    ID: {item.id || `IMG-${idx}`}
                                </span>
                            </div>
                            {/* 右侧：OCR 识别文本 */}
                            <div className="whitespace-pre-wrap font-mono text-sm overflow-auto max-h-[300px]">
                                <div className="text-xs text-blue-600 mb-1 font-bold">[OCR Content - {item.id || `IMG-${idx}`}]</div>
                                {item.text || <span className="text-gray-400 italic">No text detected</span>}
                            </div>
                        </div>
                    ))}
                </div>
            );
        }

        // 解析结果标签页（纯 Markdown，不含 OCR）
        if (tab === 'parsing') {
             let displayContent = parsingContent;

             // 兼容旧文档：如果没有 parsing_content，从 raw_content 中过滤 OCR 内容
             if (!displayContent && rawContent) {
                 displayContent = rawContent;
                 // 移除 OCR 标记行
                 displayContent = displayContent.replace(/^> \[OCR Content - IMG-[A-F0-9]+\]:.*$/gm, '');
                 // 移除 OCR 引用块
                 displayContent = displayContent.replace(/> \[OCR Content - IMG-[A-F0-9]+\]:(?:\n> .*)*\n?/g, '');
             }

             return (
                <div className="w-full h-full overflow-auto bg-white p-4 border rounded font-mono text-sm whitespace-pre-wrap">
                    <div className="mb-4 p-2 bg-blue-50 text-blue-800 text-xs rounded border border-blue-200 flex justify-between items-center">
                        <span>This is the initial parsing result (Markdown from PyMuPDF4LLM).</span>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 text-blue-700 hover:text-blue-900"
                            onClick={() => downloadFile(displayContent, `${doc.filename}_parsing.md`)}
                        >
                            <Download className="h-3 w-3 mr-1" /> Download MD
                        </Button>
                    </div>
                    {displayContent || "No content available."}
                </div>
            );
        }

        // 合并内容标签页（Markdown + OCR，未清理）
        if (tab === 'merging') {
             return (
                <div className="w-full h-full overflow-auto bg-white p-4 border rounded font-mono text-sm whitespace-pre-wrap">
                    <div className="mb-4 p-2 bg-yellow-50 text-yellow-800 text-xs rounded border border-yellow-200 flex justify-between items-center">
                        <span>This is the RAW content after merging OCR results, before cleaning.</span>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 text-yellow-700 hover:text-yellow-900"
                            onClick={() => downloadFile(rawContent, `${doc.filename}_raw.md`)}
                        >
                            <Download className="h-3 w-3 mr-1" /> Download MD
                        </Button>
                    </div>
                    {rawContent || "No raw content available."}
                </div>
            );
        }

        // 清理结果标签页（最终内容）
        return (
            <div className="w-full h-full overflow-auto bg-white p-4 border rounded font-mono text-sm whitespace-pre-wrap">
                 <div className="mb-4 p-2 bg-green-50 text-green-800 text-xs rounded border border-green-200 flex justify-between items-center">
                    <div className="flex items-center gap-2">
                        <span>This is the FINAL cleaned content used for AI analysis.</span>
                        {/* 显示清理统计信息 */}
                        {docDetails.status_message && docDetails.status_message.includes("Cleaned") && (
                            <span className="font-bold bg-green-200 px-2 py-0.5 rounded text-green-900">
                                {docDetails.status_message}
                            </span>
                        )}
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-green-700 hover:text-green-900"
                        onClick={() => downloadFile(content, `${doc.filename}_cleaned.md`)}
                    >
                        <Download className="h-3 w-3 mr-1" /> Download MD
                    </Button>
                </div>
                {content || "No content available."}
            </div>
        );
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl h-[90vh] flex flex-col">
            {/* 模态框标题和标签页切换 */}
            <div className="flex justify-between items-center p-4 border-b">
            <h3 className="text-lg font-medium">{doc.filename} - Preview</h3>
            <div className="flex space-x-2">
                {/* 标签页按钮组 */}
                <div className="bg-gray-100 rounded-lg p-1 flex space-x-1">
                    <button
                        className={`px-3 py-1 text-sm rounded-md transition-colors ${tab === 'pdf' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-900'}`}
                        onClick={() => setTab('pdf')}
                    >
                        Original PDF
                    </button>
                    <button
                        className={`px-3 py-1 text-sm rounded-md transition-colors ${tab === 'parsing' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-900'}`}
                        onClick={() => setTab('parsing')}
                        disabled={!doc.processing_stage || doc.processing_stage === 'init'}
                    >
                        Parsing Result
                    </button>
                    <button
                        className={`px-3 py-1 text-sm rounded-md transition-colors ${tab === 'ocr' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-900'}`}
                        onClick={() => setTab('ocr')}
                        disabled={!doc.ocr_data && doc.processing_stage !== 'done'}
                    >
                        OCR Details
                    </button>
                    <button
                        className={`px-3 py-1 text-sm rounded-md transition-colors ${tab === 'merging' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-900'}`}
                        onClick={() => setTab('merging')}
                        disabled={doc.processing_stage === 'init' || doc.processing_stage === 'parsing' || doc.processing_stage === 'ocr'}
                    >
                        Raw Merged
                    </button>
                    <button
                        className={`px-3 py-1 text-sm rounded-md transition-colors ${tab === 'cleaning' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-900'}`}
                        onClick={() => setTab('cleaning')}
                        disabled={doc.processing_stage !== 'done'}
                    >
                        Cleaned Result
                    </button>
                </div>
                <Button variant="ghost" size="sm" onClick={onClose}>Close</Button>
            </div>
            </div>
            {/* 内容区域 */}
            <div className="flex-1 overflow-hidden p-4 bg-gray-100">
                {renderContent()}
            </div>
        </div>
        </div>
    );
};

/**
 * 处理步骤进度组件
 * 显示文档处理的四个阶段：解析 → OCR → 合并 → 清理
 * @param {Object} doc - 文档对象
 * @param {Function} onPreview - 预览回调
 */
const ProcessingSteps = ({ doc, onPreview }) => {
  // 定义处理步骤
  const steps = [
    { id: 'parsing', label: 'PDF Parsing', tab: 'pdf' },
    { id: 'ocr', label: 'OCR Processing', tab: 'ocr' },
    { id: 'merging', label: 'Content Merging', tab: 'merging' },
    { id: 'cleaning', label: 'Cleaning', tab: 'cleaning' }
  ];

  /**
   * 获取当前处理步骤索引
   * @returns {number} 步骤索引（0-4，-1 表示失败）
   */
  const getCurrentStepIndex = () => {
    if (doc.status === 'completed') return 4;
    if (doc.status === 'failed') return -1;
    if (doc.processing_stage === 'parsing' || doc.processing_stage === 'init') return 0;
    if (doc.processing_stage === 'ocr') return 1;
    if (doc.processing_stage === 'cleaning') return 3;
    if (doc.processing_stage === 'done') return 4;
    return 0;
  };

  const currentStep = getCurrentStepIndex();

  return (
    <div className="mt-2 space-y-2">
      {/* 步骤指示器 */}
      <div className="flex items-center space-x-2 text-xs">
        {steps.map((step, index) => {
          let statusColor = "text-gray-400";
          let icon = <div className="w-2 h-2 rounded-full bg-gray-300" />;
          let isCompleted = index < currentStep;
          let isActive = index === currentStep;

          // 已完成步骤：绿色 + 勾选图标
          if (isCompleted) {
            statusColor = "text-green-600 font-medium";
            icon = <CheckCircle className="w-3 h-3" />;
          }
          // 进行中步骤：蓝色 + 旋转图标
          else if (isActive) {
            statusColor = "text-blue-600 font-medium";
            icon = <Loader2 className="w-3 h-3 animate-spin" />;
          }

          return (
            <div key={step.id} className={`flex items-center space-x-1 ${statusColor} group relative`}>
              {icon}
              <span>{step.label}</span>

              {/* 已完成步骤显示预览按钮（悬停时显示） */}
              {isCompleted && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onPreview(step.tab); }}
                    className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-blue-600 transition-opacity ml-1 p-0.5 rounded hover:bg-gray-100"
                    title={`View ${step.label} Result`}
                  >
                    <Eye className="w-3 h-3" />
                  </button>
              )}

              {/* 步骤之间的箭头 */}
              {index < steps.length - 1 && <span className="text-gray-300 mx-1">→</span>}
            </div>
          );
        })}
      </div>

      {/* 进度条（处理中时显示） */}
      {currentStep >= 0 && currentStep < 4 && doc.status === 'processing' && (
        <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
          <div
            className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${doc.progress}%` }}
          />
        </div>
      )}

      {/* 状态消息（OCR 阶段显示处理进度） */}
      {doc.status_message && currentStep === 1 && (
         <p className="text-xs text-blue-600 mt-0.5">{doc.status_message}</p>
      )}
    </div>
  );
};

/**
 * 文档上传主组件
 * @param {Object} project - 项目对象
 * @param {Array} documents - 文档列表
 * @param {Function} onUpload - 上传回调
 * @param {Function} onDelete - 删除回调
 */
export function DocumentUpload({ project, documents, onUpload, onDelete }) {
  // 文件输入框引用
  const fileInputRef = React.useRef(null);
  // 预览文档状态
  const [previewDoc, setPreviewDoc] = useState(null);
  // 预览初始标签页
  const [initialTab, setInitialTab] = useState('pdf');
  // 拖拽激活状态
  const [dragActive, setDragActive] = useState(false);

  /**
   * 打开预览模态框
   * @param {Object} doc - 文档对象
   * @param {string} tab - 初始标签页
   */
  const openPreview = (doc, tab = 'pdf') => {
      setPreviewDoc(doc);
      setInitialTab(tab);
  };

  /**
   * 处理文件选择（点击上传）
   */
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onUpload(e.target.files);
      e.target.value = null;  // 清空输入框，允许重复上传同一文件
    }
  };

  /**
   * 处理拖拽事件
   */
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
        setDragActive(true);
    } else if (e.type === "dragleave") {
        setDragActive(false);
    }
  };

  /**
   * 处理文件拖放
   */
  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        onUpload(e.dataTransfer.files);
    }
  };

  /**
   * 根据文档状态返回对应图标
   * @param {string} status - 文档状态
   * @returns {JSX.Element} 状态图标
   */
  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed': return <XCircle className="h-5 w-5 text-red-500" />;
      case 'processing': return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
      case 'uploading': return <Loader2 className="h-5 w-5 text-gray-500 animate-spin" />;
      default: return <div className="h-5 w-5 rounded-full border-2 border-gray-300" />;
    }
  };

  /**
   * 渲染文档列表
   * @param {Array} docs - 文档数组
   */
  const renderDocList = (docs) => {
    return (
        <div
            className={`mt-4 border-2 border-dashed rounded-lg p-4 transition-colors ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
        >
            {/* 上传区域标题 */}
            <div className="flex justify-between items-center mb-4">
                <div className="text-sm text-gray-500">
                    {docs.length === 0 ? "Drag & drop PDF here, or click upload" : `${docs.length} document(s) uploaded`}
                </div>
                <div>
                    {/* 隐藏的文件输入框 */}
                    <input
                        type="file"
                        accept=".pdf"
                        multiple
                        className="hidden"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                    />
                    <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                        <Upload className="mr-2 h-4 w-4" /> Upload PDF
                    </Button>
                </div>
            </div>

            {/* 文档列表 */}
            {docs.length > 0 && (
                <ul className="divide-y divide-gray-200">
                    {docs.map((doc) => (
                        <li key={doc.id} className="py-3 flex items-center justify-between">
                            {/* 文档信息 */}
                            <div className="flex items-center flex-1 min-w-0 mr-4">
                                <FileText className="h-5 w-5 text-gray-400 mr-3 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-gray-900 truncate" title={doc.filename}>{doc.filename}</p>
                                    {/* 处理进度或状态信息 */}
                                    {doc.status === 'processing' || doc.status === 'completed' ? (
                                        <ProcessingSteps doc={doc} onPreview={(tab) => openPreview(doc, tab)} />
                                    ) : (
                                        <div className="flex items-center space-x-2 mt-1">
                                            <p className="text-xs text-gray-500">
                                                Status: <span className="capitalize">{doc.status}</span>
                                            </p>
                                            {/* 错误信息 */}
                                            {doc.error_message && (
                                                <p className="text-xs text-red-500 truncate" title={doc.error_message}>{doc.error_message}</p>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                            {/* 操作按钮 */}
                            <div className="flex items-center space-x-2 flex-shrink-0">
                                {/* 预览按钮 */}
                                <Button variant="ghost" size="icon" onClick={() => openPreview(doc)} className="text-gray-400 hover:text-blue-600">
                                    <Eye className="h-4 w-4" />
                                </Button>
                                {/* 状态图标 */}
                                {getStatusIcon(doc.status)}
                                {/* 删除按钮 */}
                                <Button variant="ghost" size="icon" onClick={() => onDelete(doc.id)} className="text-gray-400 hover:text-red-600">
                                    <Trash2 className="h-4 w-4" />
                                </Button>
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
  };

  return (
    <div className="space-y-8">
      {/* 预览模态框 */}
      {previewDoc && (
        <PreviewModal
            doc={previewDoc}
            initialTab={initialTab}
            onClose={() => setPreviewDoc(null)}
        />
      )}

      {/* 文档上传区域 */}
      <div className="bg-white shadow sm:rounded-lg">
        <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">Documents</h3>
            <div className="mt-2 max-w-xl text-sm text-gray-500">
                <p>Upload PDF documents for processing.</p>
            </div>
            {renderDocList(documents)}
        </div>
      </div>
    </div>
  );
}
