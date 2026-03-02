/**
 * 项目卡片组件
 * 在首页显示单个项目的卡片，包含项目名称、描述、创建时间等信息
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { FileText, Calendar, MoreVertical } from 'lucide-react';
import { Button } from './ui/button';

export function ProjectCard({ project }) {
  return (
    <div className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow duration-200">
      {/* 卡片主体内容 */}
      <div className="px-4 py-5 sm:p-6">
        <div className="flex items-center justify-between">
          {/* 项目信息（可点击跳转到详情页） */}
          <Link to={`/project/${project.id}`} className="flex items-center">
            <div className="flex-shrink-0">
              <FileText className="h-6 w-6 text-gray-400" />
            </div>
            <div className="ml-4">
              {/* 项目名称 */}
              <h3 className="text-lg leading-6 font-medium text-gray-900">{project.name}</h3>
              {/* 创建时间 */}
              <div className="mt-1 text-sm text-gray-500 flex items-center">
                <Calendar className="flex-shrink-0 mr-1.5 h-4 w-4 text-gray-400" />
                <p>Created on {new Date(project.created_at).toLocaleDateString()}</p>
              </div>
            </div>
          </Link>
          {/* 更多操作按钮（预留） */}
          <div className="relative">
             <Button variant="ghost" size="icon">
                <MoreVertical className="h-4 w-4" />
             </Button>
          </div>
        </div>
        {/* 项目描述 */}
        <div className="mt-4">
            <p className="text-sm text-gray-500 line-clamp-2">
                {project.description || "No description provided."}
            </p>
        </div>
      </div>
      {/* 卡片底部操作区 */}
      <div className="bg-gray-50 px-4 py-4 sm:px-6 flex justify-end space-x-2">
          <Link to={`/project/${project.id}`}>
            <Button variant="outline" size="sm">Open</Button>
          </Link>
      </div>
    </div>
  );
}
