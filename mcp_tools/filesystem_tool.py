import httpx
import os
import re
from typing import Dict, Any, Optional
from .base_tool import BaseMCPTool

class FilesystemTool(BaseMCPTool):
    """增强的文件系统操作工具"""
    
    @property
    def tool_name(self) -> str:
        return "文件系统工具"
    
    @property
    def description(self) -> str:
        return "全功能文件系统操作工具，支持文件和文件夹的创建、读取、写入、移动、重命名、搜索等操作"
    
    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "list_directory": {
                "description": "列出指定目录中的文件和文件夹",
                "parameters": {
                    "path": {
                        "type": "string",
                        "description": "要列出内容的目录路径，默认为用户桌面",
                        "required": False
                    }
                },
                "examples": [
                    "查看桌面上有什么文件",
                    "列出当前目录的内容",
                    "显示文件夹中的文件",
                    "桌面有哪些文件和文件夹"
                ]
            },
            "read_file": {
                "description": "读取文件内容",
                "parameters": {
                    "file_path": {
                        "type": "string",
                        "description": "要读取的文件路径",
                        "required": True
                    }
                },
                "examples": [
                    "读取桌面上的1.txt文件",
                    "查看文档内容",
                    "打开某个文件看看内容"
                ]
            },
            "write_file": {
                "description": "写入内容到文件",
                "parameters": {
                    "file_path": {
                        "type": "string",
                        "description": "要写入的文件路径",
                        "required": True
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的内容",
                        "required": True
                    },
                    "mode": {
                        "type": "string",
                        "description": "写入模式：'overwrite'(覆盖)或'append'(追加)",
                        "required": False
                    }
                },
                "examples": [
                    "在桌面创建一个记事本文件",
                    "向文件中添加内容",
                    "保存文本到文件"
                ]
            },
            "create_file": {
                "description": "创建新文件",
                "parameters": {
                    "file_name": {
                        "type": "string",
                        "description": "文件名",
                        "required": True
                    },
                    "content": {
                        "type": "string",
                        "description": "文件内容",
                        "required": False
                    },
                    "file_type": {
                        "type": "string",
                        "description": "文件类型扩展名，如txt, md, py等",
                        "required": False
                    },
                    "location": {
                        "type": "string",
                        "description": "文件位置，默认为桌面",
                        "required": False
                    }
                },
                "examples": [
                    "在桌面创建一个新的文本文件",
                    "创建一个Python脚本文件",
                    "新建一个记事本"
                ]
            },
            "create_directory": {
                "description": "创建新文件夹",
                "parameters": {
                    "folder_name": {
                        "type": "string",
                        "description": "文件夹名称",
                        "required": True
                    },
                    "location": {
                        "type": "string",
                        "description": "创建位置，默认为桌面",
                        "required": False
                    }
                },
                "examples": [
                    "在桌面创建一个新文件夹",
                    "建立一个项目目录",
                    "新建文件夹"
                ]
            },
            "move_file": {
                "description": "移动文件或文件夹",
                "parameters": {
                    "file_name": {
                        "type": "string",
                        "description": "要移动的文件或文件夹名",
                        "required": True
                    },
                    "source_location": {
                        "type": "string",
                        "description": "源位置",
                        "required": False
                    },
                    "destination_location": {
                        "type": "string",
                        "description": "目标位置",
                        "required": True
                    }
                },
                "examples": [
                    "把文件移动到某个文件夹",
                    "将桌面的文件放到指定目录",
                    "移动文件到其他位置"
                ]
            },
            "rename_file": {
                "description": "重命名文件或文件夹",
                "parameters": {
                    "old_name": {
                        "type": "string",
                        "description": "原文件名",
                        "required": True
                    },
                    "new_name": {
                        "type": "string",
                        "description": "新文件名",
                        "required": True
                    },
                    "location": {
                        "type": "string",
                        "description": "文件位置，默认为桌面",
                        "required": False
                    }
                },
                "examples": [
                    "重命名桌面上的文件",
                    "将文件改名为新名称",
                    "修改文件名"
                ]
            },
            "search_files": {
                "description": "搜索文件和文件夹",
                "parameters": {
                    "pattern": {
                        "type": "string",
                        "description": "搜索模式或关键词",
                        "required": True
                    },
                    "search_path": {
                        "type": "string",
                        "description": "搜索路径，默认为桌面",
                        "required": False
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "description": "要排除的模式列表",
                        "required": False
                    }
                },
                "examples": [
                    "搜索桌面上所有txt文件",
                    "查找包含特定关键词的文件",
                    "找到所有图片文件"
                ]
            },
            "get_file_info": {
                "description": "获取文件或文件夹的详细信息",
                "parameters": {
                    "file_path": {
                        "type": "string",
                        "description": "文件或文件夹路径",
                        "required": True
                    }
                },
                "examples": [
                    "查看文件的详细信息",
                    "获取文件大小和创建时间",
                    "查看文件属性"
                ]
            }
        }
    
    async def execute_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行文件系统操作"""
        function_map = {
            "list_directory": self._list_directory,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "create_file": self._create_file,
            "create_directory": self._create_directory,
            "move_file": self._move_file,
            "rename_file": self._rename_file,
            "search_files": self._search_files,
            "get_file_info": self._get_file_info
        }
        
        if function_name in function_map:
            return await function_map[function_name](parameters)
        else:
            return {
                "status": "error",
                "message": f"未知函数: {function_name}"
            }
    
    def _parse_path(self, user_input: str, default_base: str = None) -> str:
        """
        智能路径解析函数，支持多种中文表达方式
        支持"桌面上的xxx"、"桌面上的文件夹X"、"名为X的文件夹(里|内)"等表达式
        """
        if not user_input:
            return default_base or "C:\\Users\\Jason\\Desktop"
        
        user_input = user_input.strip()
        desktop_path_base = "C:\\Users\\Jason\\Desktop"
        
        # 处理 "桌面/文件名" 格式
        if re.match(r'^(?:桌面|desktop)[/\\](.+)$', user_input, re.IGNORECASE):
            filename_match = re.match(r'^(?:桌面|desktop)[/\\](.+)$', user_input, re.IGNORECASE)
            return os.path.join(desktop_path_base, filename_match.group(1))
        
        # 处理已经包含桌面路径但有错误的情况
        if desktop_path_base.lower() in user_input.lower():
            corrected_path = user_input.replace('/', '\\')
            
            if corrected_path.lower().startswith(desktop_path_base.lower()):
                remaining_path = corrected_path[len(desktop_path_base):].lstrip('\\')
                
                if remaining_path.lower().startswith('desktop\\'):
                    filename = remaining_path[8:]
                    return os.path.join(desktop_path_base, filename)
                elif remaining_path.lower().startswith('desktop/'):
                    filename = remaining_path[8:]
                    return os.path.join(desktop_path_base, filename)
                elif remaining_path.startswith('桌面\\'):
                    filename = remaining_path[3:]
                    return os.path.join(desktop_path_base, filename)
                elif remaining_path.startswith('桌面/'):
                    filename = remaining_path[3:]
                    return os.path.join(desktop_path_base, filename)
                else:
                    return corrected_path
            
            return corrected_path
        
        # 定义文件/文件夹描述词
        file_descriptors = r'(?:文件|文档)'
        folder_descriptors = r'(?:文件夹|目录)'
        
        # 匹配 "桌面上的..." 格式
        match_desktop_prefix = re.match(r'^(?:桌面|desktop)上的?\s*(.*)$', user_input, re.IGNORECASE)
        if match_desktop_prefix:
            name_part = match_desktop_prefix.group(1).strip()
            
            # "名为X的文件夹" 模式
            match_named_folder = re.match(r'^名为(.+?)的文件夹[里内]?$', name_part)
            if match_named_folder:
                return os.path.join(desktop_path_base, match_named_folder.group(1).strip())
            
            # 文件描述词模式
            match_file = re.match(rf'^{file_descriptors}\s*(.+)$', name_part, re.IGNORECASE)
            if match_file:
                return os.path.join(desktop_path_base, match_file.group(1).strip())
            
            # 文件夹描述词模式
            match_folder = re.match(rf'^{folder_descriptors}\s*(.+)$', name_part, re.IGNORECASE)
            if match_folder:
                return os.path.join(desktop_path_base, match_folder.group(1).strip())
            
            # 直接名称
            if name_part:
                return os.path.join(desktop_path_base, name_part)
        
        # 直接匹配 "名为X的文件夹"
        match_named_folder_direct = re.match(r'^名为(.+?)的文件夹[里内]?$', user_input)
        if match_named_folder_direct:
            return os.path.join(desktop_path_base, match_named_folder_direct.group(1).strip())
        
        # 绝对路径
        if os.path.isabs(user_input):
            return user_input.replace('/', '\\')
        
        # 默认桌面路径
        return os.path.join(desktop_path_base, user_input)
    
    async def _list_directory(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """列出目录内容"""
        try:
            path = parameters.get("path", "C:\\Users\\Jason\\Desktop")
            path = self._parse_path(path)
            
            # 请求MCPO Filesystem服务
            endpoints = [
                f"{self.base_url}/filesystem/list_directory",
                f"{self.base_url}/list_directory"
            ]
            
            for endpoint in endpoints:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.post(
                            endpoint,
                            json={"path": path}
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            
                            if isinstance(result, dict) and "error" in result:
                                continue  # 尝试下一个端点
                            
                            # 格式化返回结果
                            return await self._format_directory_listing(result, path)
                            
                except Exception as e:
                    self.logger.warning(f"尝试端点 {endpoint} 失败: {str(e)}")
                    continue
            
            return {
                "status": "error",
                "message": "无法连接到文件系统服务，所有端点都失败"
            }
                
        except Exception as e:
            self.logger.error(f"列出目录错误: {e}")
            return {
                "status": "error",
                "message": f"列出目录失败: {str(e)}"
            }
    
    async def _format_directory_listing(self, file_list: Any, path: str) -> Dict[str, Any]:
        """格式化目录列表"""
        try:
            # 处理不同格式的返回数据
            if isinstance(file_list, dict) and 'content' in file_list:
                file_content = file_list['content']
            elif isinstance(file_list, str):
                file_content = file_list
            elif isinstance(file_list, list):
                file_content = None
                items = file_list
            else:
                items = []
                file_content = None
            
            # 如果有字符串内容，按行分割
            if file_content is not None:
                items = file_content.strip().split('\n')
            
            formatted_files = []
            directories = []
            files = []
            
            for item in items:
                if not item or not item.strip():
                    continue
                    
                item = item.strip()
                
                if item.startswith('[DIR]'):
                    name = item[5:].strip()
                    if name:
                        directories.append(name)
                        formatted_files.append(f"📁 {name}")
                elif item.startswith('[FILE]'):
                    name = item[6:].strip()
                    if name:
                        files.append(name)
                        formatted_files.append(f"📄 {name}")
                else:
                    # 无标记，当作文件处理
                    if item:
                        files.append(item)
                        formatted_files.append(f"📄 {item}")
            
            return {
                "status": "success",
                "path": path,
                "directories": directories,
                "files": files,
                "formatted_list": formatted_files,
                "total_count": len(directories) + len(files)
            }
            
        except Exception as e:
            self.logger.error(f"格式化目录列表错误: {e}")
            return {
                "status": "error",
                "message": f"格式化目录列表失败: {str(e)}"
            }
    
    async def _read_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """读取文件内容"""
        try:
            file_path = parameters.get("file_path")
            if not file_path:
                return {
                    "status": "error",
                    "message": "文件路径不能为空"
                }
            
            file_path = self._parse_path(file_path)
            
            # 检查文件类型
            if file_path.lower().endswith(('.docx', '.xlsx', '.pdf', '.doc', '.xls')):
                return {
                    "status": "error",
                    "message": f"无法读取二进制文件 {file_path}，请使用专门的软件打开"
                }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/filesystem/read_file",
                    json={"path": file_path}
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"读取文件失败: HTTP {response.status_code}"
                    }
                
                result = response.json()
                
                if isinstance(result, dict) and "error" in result:
                    return {
                        "status": "error",
                        "message": result["error"]
                    }
                
                return {
                    "status": "success",
                    "file_path": file_path,
                    "content": result,
                    "size": len(str(result)) if result else 0
                }
                
        except Exception as e:
            self.logger.error(f"读取文件错误: {e}")
            return {
                "status": "error",
                "message": f"读取文件失败: {str(e)}"
            }
    
    async def _write_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """写入文件内容"""
        try:
            file_path = parameters.get("file_path")
            content = parameters.get("content", "")
            mode = parameters.get("mode", "overwrite")  # overwrite 或 append
            
            if not file_path:
                return {
                    "status": "error",
                    "message": "文件路径不能为空"
                }
            
            file_path = self._parse_path(file_path)
            
            # 检查文件类型
            if file_path.lower().endswith(('.docx', '.xlsx', '.pdf', '.doc', '.xls')):
                return {
                    "status": "error",
                    "message": f"无法写入二进制文件 {file_path}，这会损坏文件"
                }
            
            final_content = content
            
            # 如果是追加模式，先读取现有内容
            if mode == "append":
                try:
                    read_result = await self._read_file({"file_path": file_path})
                    if read_result.get("status") == "success":
                        existing_content = read_result.get("content", "")
                        final_content = str(existing_content) + str(content)
                except:
                    pass  # 如果读取失败，使用新内容
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/filesystem/write_file",
                    json={"path": file_path, "content": final_content}
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"写入文件失败: HTTP {response.status_code}"
                    }
                
                result = response.json()
                
                if isinstance(result, dict) and "error" in result:
                    return {
                        "status": "error",
                        "message": result["error"]
                    }
                
                return {
                    "status": "success",
                    "file_path": file_path,
                    "mode": mode,
                    "content_length": len(final_content)
                }
                
        except Exception as e:
            self.logger.error(f"写入文件错误: {e}")
            return {
                "status": "error",
                "message": f"写入文件失败: {str(e)}"
            }
    
    async def _create_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """创建新文件"""
        try:
            file_name = parameters.get("file_name")
            content = parameters.get("content", "")
            file_type = parameters.get("file_type", "txt")
            location = parameters.get("location", "desktop")
            
            if not file_name:
                return {
                    "status": "error",
                    "message": "文件名不能为空"
                }
            
            # 如果文件名没有扩展名，添加扩展名
            if not os.path.splitext(file_name)[1]:
                file_name = f"{file_name}.{file_type}"
            
            # 构建完整路径
            if location == "desktop" or "桌面" in str(location):
                full_path = os.path.join("C:\\Users\\Jason\\Desktop", file_name)
            else:
                full_path = self._parse_path(os.path.join(location, file_name))
            
            # 使用写入文件功能创建
            return await self._write_file({
                "file_path": full_path,
                "content": content,
                "mode": "overwrite"
            })
            
        except Exception as e:
            self.logger.error(f"创建文件错误: {e}")
            return {
                "status": "error",
                "message": f"创建文件失败: {str(e)}"
            }
    
    async def _create_directory(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """创建新目录"""
        try:
            folder_name = parameters.get("folder_name")
            location = parameters.get("location", "desktop")
            
            if not folder_name:
                return {
                    "status": "error",
                    "message": "文件夹名称不能为空"
                }
            
            # 构建完整路径
            if location == "desktop" or "桌面" in str(location):
                full_path = os.path.join("C:\\Users\\Jason\\Desktop", folder_name)
            else:
                full_path = self._parse_path(os.path.join(location, folder_name))
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/filesystem/create_directory",
                    json={"path": full_path}
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"创建目录失败: HTTP {response.status_code}"
                    }
                
                result = response.json()
                
                if isinstance(result, dict) and "error" in result:
                    return {
                        "status": "error",
                        "message": result["error"]
                    }
                
                return {
                    "status": "success",
                    "folder_path": full_path,
                    "folder_name": folder_name
                }
                
        except Exception as e:
            self.logger.error(f"创建目录错误: {e}")
            return {
                "status": "error",
                "message": f"创建目录失败: {str(e)}"
            }
    
    async def _move_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """移动文件或文件夹"""
        try:
            file_name = parameters.get("file_name")
            source_location = parameters.get("source_location", "desktop")
            destination_location = parameters.get("destination_location")
            
            if not file_name:
                return {
                    "status": "error",
                    "message": "文件名不能为空"
                }
            
            if not destination_location:
                return {
                    "status": "error",
                    "message": "目标位置不能为空"
                }
            
            # 构建源文件路径
            if source_location == "desktop" or "桌面" in str(source_location):
                source_path = os.path.join("C:\\Users\\Jason\\Desktop", file_name)
            else:
                source_path = self._parse_path(os.path.join(source_location, file_name))
            
            # 构建目标路径
            if destination_location.startswith("desktop/"):
                folder_name = destination_location.replace("desktop/", "")
                destination_path = os.path.join("C:\\Users\\Jason\\Desktop", folder_name, file_name)
            elif destination_location == "desktop":
                destination_path = os.path.join("C:\\Users\\Jason\\Desktop", file_name)
            else:
                destination_path = self._parse_path(os.path.join(destination_location, file_name))
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/filesystem/move_file",
                    json={"source": source_path, "destination": destination_path}
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"移动文件失败: HTTP {response.status_code}"
                    }
                
                result = response.json()
                
                if isinstance(result, dict) and "error" in result:
                    return {
                        "status": "error",
                        "message": result["error"]
                    }
                
                return {
                    "status": "success",
                    "source_path": source_path,
                    "destination_path": destination_path,
                    "file_name": file_name
                }
                
        except Exception as e:
            self.logger.error(f"移动文件错误: {e}")
            return {
                "status": "error",
                "message": f"移动文件失败: {str(e)}"
            }
    
    async def _rename_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """重命名文件或文件夹"""
        try:
            old_name = parameters.get("old_name")
            new_name = parameters.get("new_name")
            location = parameters.get("location", "desktop")
            
            if not old_name or not new_name:
                return {
                    "status": "error",
                    "message": "原文件名和新文件名都不能为空"
                }
            
            # 构建路径
            if location == "desktop" or "桌面" in str(location):
                old_path = os.path.join("C:\\Users\\Jason\\Desktop", old_name)
                new_path = os.path.join("C:\\Users\\Jason\\Desktop", new_name)
            else:
                old_path = self._parse_path(os.path.join(location, old_name))
                new_path = self._parse_path(os.path.join(location, new_name))
            
            # 重命名实际上是移动操作
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/filesystem/move_file",
                    json={"source": old_path, "destination": new_path}
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"重命名失败: HTTP {response.status_code}"
                    }
                
                result = response.json()
                
                if isinstance(result, dict) and "error" in result:
                    return {
                        "status": "error",
                        "message": result["error"]
                    }
                
                return {
                    "status": "success",
                    "old_name": old_name,
                    "new_name": new_name,
                    "old_path": old_path,
                    "new_path": new_path
                }
                
        except Exception as e:
            self.logger.error(f"重命名文件错误: {e}")
            return {
                "status": "error",
                "message": f"重命名文件失败: {str(e)}"
            }
    
    async def _search_files(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """搜索文件和文件夹"""
        try:
            pattern = parameters.get("pattern")
            search_path = parameters.get("search_path", "C:\\Users\\Jason\\Desktop")
            exclude_patterns = parameters.get("exclude_patterns", [])
            
            if not pattern:
                return {
                    "status": "error",
                    "message": "搜索模式不能为空"
                }
            
            search_path = self._parse_path(search_path)
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/filesystem/search_files",
                    json={
                        "path": search_path,
                        "pattern": pattern,
                        "excludePatterns": exclude_patterns
                    }
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"搜索文件失败: HTTP {response.status_code}"
                    }
                
                result = response.json()
                
                if isinstance(result, dict) and "error" in result:
                    return {
                        "status": "error",
                        "message": result["error"]
                    }
                
                return {
                    "status": "success",
                    "search_path": search_path,
                    "pattern": pattern,
                    "results": result,
                    "count": len(result) if isinstance(result, list) else 0
                }
                
        except Exception as e:
            self.logger.error(f"搜索文件错误: {e}")
            return {
                "status": "error",
                "message": f"搜索文件失败: {str(e)}"
            }
    
    async def _get_file_info(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """获取文件或文件夹信息"""
        try:
            file_path = parameters.get("file_path")
            
            if not file_path:
                return {
                    "status": "error",
                    "message": "文件路径不能为空"
                }
            
            file_path = self._parse_path(file_path)
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/filesystem/get_file_info",
                    json={"path": file_path}
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"获取文件信息失败: HTTP {response.status_code}"
                    }
                
                result = response.json()
                
                if isinstance(result, dict) and "error" in result:
                    return {
                        "status": "error",
                        "message": result["error"]
                    }
                
                return {
                    "status": "success",
                    "file_path": file_path,
                    "info": result
                }
                
        except Exception as e:
            self.logger.error(f"获取文件信息错误: {e}")
            return {
                "status": "error",
                "message": f"获取文件信息失败: {str(e)}"
            } 