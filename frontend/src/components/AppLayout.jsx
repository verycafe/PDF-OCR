import React from 'react';
import { Link, Outlet } from 'react-router-dom';
import { FileText } from 'lucide-react';

export default function AppLayout() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 font-sans">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <Link to="/" className="flex-shrink-0 flex items-center group">
                <FileText className="h-8 w-8 text-blue-600 mr-2 group-hover:text-blue-700 transition-colors" />
                <span className="font-bold text-xl text-gray-900 group-hover:text-blue-700 transition-colors">PDF-OCR</span>
              </Link>
            </div>
            <div className="flex items-center space-x-4">
              {/* Future: User Profile or Settings */}
              <span className="text-sm text-gray-500">v0.1.0</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
