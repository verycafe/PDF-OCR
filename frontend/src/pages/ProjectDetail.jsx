/**
 * 项目详情页组件
 * 显示项目信息和文档上传/管理界面
 * 支持实时轮询更新文档处理状态
 */
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { projectsApi, documentsApi } from '../api';
import { DocumentUpload } from '../components/DocumentUpload';

export default function ProjectDetail() {
  // 从 URL 获取项目 ID
  const { id } = useParams();
  // 项目信息状态
  const [project, setProject] = useState(null);
  // 文档列表状态
  const [documents, setDocuments] = useState([]);
  // 正在上传的文档（临时状态）
  const [uploadingDocs, setUploadingDocs] = useState([]);
  // 加载状态
  const [loading, setLoading] = useState(true);

  // 组件挂载时获取项目数据，并启动定时轮询
  useEffect(() => {
    fetchProjectData();

    // 每 2 秒轮询一次文档状态（用于实时更新处理进度）
    const interval = setInterval(fetchDocuments, 2000);
    // 组件卸载时清理定时器
    return () => clearInterval(interval);
  }, [id]);

  /**
   * 获取项目和文档数据（初始加载）
   */
  const fetchProjectData = async () => {
    try {
      // 并行请求项目信息和文档列表
      const [projRes, docRes] = await Promise.all([
        projectsApi.get(id),
        documentsApi.list(id)
      ]);
      setProject(projRes.data);
      setDocuments(docRes.data);
    } catch (error) {
      console.error("Failed to load project:", error);
    } finally {
      setLoading(false);
    }
  };

  /**
   * 获取文档列表（轮询更新）
   */
  const fetchDocuments = async () => {
      try {
          const res = await documentsApi.list(id);
          setDocuments(res.data);
      } catch (error) {
          console.error("Failed to update documents:", error);
      }
  }

  /**
   * 处理文件上传
   * @param {FileList|Array} files - 要上传的文件列表
   */
  const handleUpload = async (files) => {
    try {
      const newUploadingDocs = [];
      const fileList = (files instanceof FileList || Array.isArray(files)) ? files : [files];

      // 为每个文件创建临时上传状态
      for (let i = 0; i < fileList.length; i++) {
        newUploadingDocs.push({
          id: `temp-${Date.now()}-${i}`,  // 临时 ID
          filename: fileList[i].name,
          status: 'uploading',
          progress: 0
        });
      }

      // 添加到上传列表（立即显示在 UI 中）
      setUploadingDocs(prev => [...prev, ...newUploadingDocs]);

      // 调用上传 API
      await documentsApi.upload(id, files);

      // 上传成功后移除临时状态
      setUploadingDocs(prev => prev.filter(d => !newUploadingDocs.find(n => n.id === d.id)));
      // 刷新文档列表
      fetchDocuments();
    } catch (error) {
      console.error("Upload failed:", error);
      alert("Upload failed");
      setUploadingDocs([]);
    }
  };

  // 合并真实文档和正在上传的文档
  const allDocuments = [...documents];

  uploadingDocs.forEach(uDoc => {
      // 避免重复显示（如果文件名已存在）
      if (!documents.find(d => d.filename === uDoc.filename)) {
          allDocuments.push(uDoc);
      }
  });

  /**
   * 处理文档删除
   * @param {string|number} docId - 文档 ID
   */
  const handleDelete = async (docId) => {
    // 如果是临时上传状态，直接从列表移除
    if (docId.toString().startsWith('temp-')) {
        setUploadingDocs(prev => prev.filter(d => d.id !== docId));
        return;
    }

    // 确认删除
    if (confirm("Are you sure you want to delete this document?")) {
        try {
            await documentsApi.delete(docId);
            fetchDocuments();
        } catch (error) {
            console.error("Delete failed:", error);
        }
    }
  };

  // 加载状态和错误处理
  if (loading) return <div className="text-center py-10">Loading project...</div>;
  if (!project) return <div className="text-center py-10">Project not found</div>;

  return (
    <div className="space-y-6">
      {/* 项目标题和描述 */}
      <div className="flex items-center justify-between">
        <div>
            <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
            <p className="text-sm text-gray-500 mt-1">{project.description}</p>
        </div>
      </div>

      {/* 文档上传和管理组件 */}
      <DocumentUpload
          project={project}
          documents={allDocuments}
          onUpload={handleUpload}
          onDelete={handleDelete}
      />
    </div>
  );
}
