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
        alert("Please enter a project name");
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
      alert("Failed to create project: " + (error.response?.data?.error || error.message));
    }
  };

  return (
    <div className="space-y-6">
      {/* 页面标题和创建按钮 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <Button onClick={() => setIsModalOpen(true)}>
          <Plus className="mr-2 h-4 w-4" /> New Project
        </Button>
      </div>

      {/* 项目列表或空状态 */}
      {loading ? (
        <div className="text-center py-10">Loading projects...</div>
      ) : projects.length === 0 ? (
        // 空状态提示
        <div className="text-center py-10 bg-white rounded-lg border border-dashed border-gray-300">
          <FileText className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No projects</h3>
          <p className="mt-1 text-sm text-gray-500">Get started by creating a new project.</p>
          <div className="mt-6">
            <Button onClick={() => setIsModalOpen(true)}>
              <Plus className="mr-2 h-4 w-4" /> New Project
            </Button>
          </div>
        </div>
      ) : (
        // 项目卡片网格
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}

      {/* 创建项目模态框 */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">Create New Project</h2>
            <form onSubmit={handleCreateProject}>
              <div className="space-y-4">
                {/* 项目名称输入 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700">Project Name</label>
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
                  <label className="block text-sm font-medium text-gray-700">Description</label>
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
                <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>Cancel</Button>
                <Button type="submit">
                  <Plus className="mr-2 h-4 w-4" /> Create Project
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
