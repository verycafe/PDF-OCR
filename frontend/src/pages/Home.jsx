/**
 * 首页组件 - 项目列表和创建
 * 显示所有项目的卡片列表，支持创建新项目
 */
import React, { useState, useEffect } from 'react';
import { Plus, FileText } from 'lucide-react';
import { Button } from '../components/ui/button';
import { ProjectCard } from '../components/ProjectCard';
import { projectsApi } from '../api';

export default function Home() {
  // 项目列表状态
  const [projects, setProjects] = useState([]);
  // 加载状态
  const [loading, setLoading] = useState(true);
  // 创建项目模态框状态
  const [isModalOpen, setIsModalOpen] = useState(false);
  // 新项目表单数据
  const [newProject, setNewProject] = useState({ name: '', description: '' });

  // 组件挂载时获取项目列表
  useEffect(() => {
    fetchProjects();
  }, []);

  /**
   * 获取项目列表
   */
  const fetchProjects = async () => {
    try {
      const response = await projectsApi.list();
      setProjects(response.data);
    } catch (error) {
      console.error('Failed to fetch projects:', error);
    } finally {
      setLoading(false);
    }
  };

  /**
   * 处理创建项目表单提交
   */
  const handleCreateProject = async (e) => {
    e.preventDefault();
    console.log("Submitting form with data:", newProject);

    // 验证项目名称
    if (!newProject.name) {
        alert("请输入项目名称");
        return;
    }

    try {
      // 调用 API 创建项目
      await projectsApi.create(newProject);
      // 关闭模态框并重置表单
      setIsModalOpen(false);
      setNewProject({ name: '', description: '' });
      // 刷新项目列表
      fetchProjects();
    } catch (error) {
      console.error('Failed to create project:', error);
      alert("创建项目失败：" + (error.response?.data?.error || error.message));
    }
  };

  /**
   * 删除项目
   * @param {Object} project - 项目对象
   */
  const handleDeleteProject = async (project) => {
    if (!confirm(`确定要删除项目“${project.name}”吗？`)) {
      return;
    }

    try {
      await projectsApi.delete(project.id);
      fetchProjects();
    } catch (error) {
      if (error.response?.status === 409 && error.response?.data?.code === 'project_has_active_documents') {
        const shouldForceDelete = confirm(
          `项目“${project.name}”里还有文档正在处理中。\n如果继续删除，系统会终止这些任务并删除项目文件。\n\n确定继续删除吗？`
        );

        if (!shouldForceDelete) {
          return;
        }

        try {
          await projectsApi.delete(project.id, { force: true });
          fetchProjects();
          return;
        } catch (forceDeleteError) {
          console.error('Failed to force delete project:', forceDeleteError);
          alert("强制删除项目失败：" + (forceDeleteError.response?.data?.error || forceDeleteError.message));
          return;
        }
      }

      console.error('Failed to delete project:', error);
      alert("删除项目失败：" + (error.response?.data?.error || error.message));
    }
  };

  return (
    <div className="space-y-6">
      {/* 页面标题和创建按钮 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">项目</h1>
        <Button onClick={() => setIsModalOpen(true)}>
          <Plus className="mr-2 h-4 w-4" /> 新建项目
        </Button>
      </div>

      {/* 项目列表或空状态 */}
      {loading ? (
        <div className="text-center py-10">项目加载中...</div>
      ) : projects.length === 0 ? (
        // 空状态提示
        <div className="text-center py-10 bg-white rounded-lg border border-dashed border-gray-300">
          <FileText className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">还没有项目</h3>
          <p className="mt-1 text-sm text-gray-500">先创建一个项目开始使用吧。</p>
          <div className="mt-6">
            <Button onClick={() => setIsModalOpen(true)}>
              <Plus className="mr-2 h-4 w-4" /> 新建项目
            </Button>
          </div>
        </div>
      ) : (
        // 项目卡片网格
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onDelete={handleDeleteProject}
            />
          ))}
        </div>
      )}

      {/* 创建项目模态框 */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">新建项目</h2>
            <form onSubmit={handleCreateProject}>
              <div className="space-y-4">
                {/* 项目名称输入 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700">项目名称</label>
                  <input
                    type="text"
                    required
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                    value={newProject.name}
                    onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
                  />
                </div>
                {/* 项目描述输入 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700">项目描述</label>
                  <textarea
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                    rows={3}
                    value={newProject.description}
                    onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
                  />
                </div>
              </div>
              {/* 表单按钮 */}
              <div className="mt-6 flex justify-end space-x-3">
                <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>取消</Button>
                <Button type="submit">
                  <Plus className="mr-2 h-4 w-4" /> 创建项目
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
