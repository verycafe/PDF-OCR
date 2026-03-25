/**
 * 项目卡片组件
 * 在首页显示单个项目的卡片，包含项目名称、描述、创建时间等信息
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { FileText, Calendar, Trash2 } from 'lucide-react';
import { Button } from './ui/button';

export function ProjectCard({ project, onDelete }) {
  return (
    <div className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow duration-200">
      {/* 卡片主体内容 */}
      <div className="px-4 py-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          {/* 项目信息（可点击跳转到详情页） */}
          <Link to={`/project/${project.id}`} className="flex items-center min-w-0">
            <div className="flex-shrink-0">
              <FileText className="h-6 w-6 text-gray-400" />
            </div>
            <div className="ml-4 min-w-0">
              {/* 项目名称 */}
              <h3 className="text-lg leading-6 font-medium text-gray-900 truncate">{project.name}</h3>
              {/* 创建时间 */}
              <div className="mt-1 text-sm text-gray-500 flex items-center">
                <Calendar className="flex-shrink-0 mr-1.5 h-4 w-4 text-gray-400" />
                <p>创建于 {new Date(project.created_at).toLocaleDateString()}</p>
              </div>
            </div>
          </Link>
        </div>
        {/* 项目描述 */}
        <div className="mt-4">
            <p className="text-sm text-gray-500 line-clamp-2">
                {project.description || "暂无项目描述"}
            </p>
        </div>
      </div>
      {/* 卡片底部操作区 */}
      <div className="bg-gray-50 px-4 py-4 sm:px-6 flex justify-end space-x-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onDelete?.(project)}
            className="text-gray-400 hover:text-red-600"
            title="删除项目"
            aria-label="删除项目"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <Link to={`/project/${project.id}`}>
            <Button variant="outline" size="sm">打开</Button>
          </Link>
      </div>
    </div>
  );
}
