/**
 * API 客户端配置和接口定义
 * 使用 axios 封装所有后端 API 调用
 */
import axios from 'axios';

// 创建 axios 实例，配置基础 URL 和默认请求头
const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * 项目相关 API
 */
export const projectsApi = {
  // 获取所有项目列表
  list: () => api.get('/projects/'),
  // 创建新项目
  create: (data) => api.post('/projects/', data),
  // 获取单个项目详情
  get: (id) => api.get(`/projects/${id}`),
  // 获取项目 Markdown 批量下载链接
  getMarkdownArchiveUrl: (id) => `/api/projects/${id}/markdown-archive`,
  // 更新项目信息
  update: (id, data) => api.put(`/projects/${id}`, data),
  // 删除项目
  delete: (id, params = {}) => api.delete(`/projects/${id}`, { params }),
};

/**
 * 文档相关 API
 */
export const documentsApi = {
  /**
   * 上传文档到指定项目
   * @param {number} projectId - 项目 ID
   * @param {FileList|Array|File} files - 要上传的文件
   * @returns {Promise} 上传结果
   */
  upload: (projectId, files) => {
    const formData = new FormData();

    // 处理多文件上传
    if (files instanceof FileList || Array.isArray(files)) {
      for (let i = 0; i < files.length; i++) {
        formData.append('file', files[i]);
      }
    } else {
      // 单文件上传
      formData.append('file', files);
    }

    return api.post(`/documents/upload/${projectId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  // 获取项目下的所有文档列表
  list: (projectId) => api.get(`/documents/project/${projectId}`),
  // 删除文档
  delete: (id) => api.delete(`/documents/${id}`),
  // 获取预览 PDF 文件 URL（DOC/DOCX 会先转换为 PDF）
  getFileUrl: (id) => `/api/documents/${id}/file`,
  // 获取最终 Markdown 下载 URL
  getMarkdownDownloadUrl: (id) => `/api/documents/${id}/markdown`,
  // 获取文档中提取的图片 URL
  getImageUrl: (id, imageName) => `/api/documents/${id}/images/${imageName}`,
  // 获取文档的所有处理内容（解析、OCR、合并、清理结果）
  getContent: (id) => api.get(`/documents/${id}/content`),
};

export default api;
