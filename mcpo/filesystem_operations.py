import requests
import logging
import traceback

# 配置日志
logger = logging.getLogger(__name__)

# MCP Filesystem服务配置
MCP_FILESYSTEM_URL = "http://127.0.0.1:8000/filesystem"

def read_file(path):
    """使用MCP Filesystem读取文件内容"""
    try:
        logger.info(f"使用MCP Filesystem读取文件: {path}")
        
        # 准备请求体
        request_body = {
            "path": path
        }
        
        # 发送请求
        response = requests.post(
            f"{MCP_FILESYSTEM_URL}/read_file",
            json=request_body,
            timeout=30
        )
        
        logger.info(f"MCP Filesystem响应状态码: {response.status_code}")
        
        # 处理响应
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"MCP Filesystem错误响应: {error_text}")
            return {"error": f"MCP服务返回HTTP错误: {response.status_code} - {error_text[:100]}"}
        
        # 获取响应内容
        try:
            result = response.json()
            return result
        except ValueError:
            text_content = response.text
            logger.info(f"MCP返回了非JSON内容，长度: {len(text_content)}")
            return text_content
    
    except Exception as e:
        logger.error(f"读取文件异常: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}

def write_file(path, content):
    """使用MCP Filesystem写入文件内容"""
    try:
        logger.info(f"使用MCP Filesystem写入文件: {path}")
        
        # 准备请求体
        request_body = {
            "path": path,
            "content": content
        }
        
        # 发送请求
        response = requests.post(
            f"{MCP_FILESYSTEM_URL}/write_file",
            json=request_body,
            timeout=30
        )
        
        logger.info(f"MCP Filesystem响应状态码: {response.status_code}")
        
        # 处理响应
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"MCP Filesystem错误响应: {error_text}")
            return {"error": f"MCP服务返回HTTP错误: {response.status_code} - {error_text[:100]}"}
        
        # 获取响应内容
        try:
            result = response.json()
            return result
        except ValueError:
            text_content = response.text
            logger.info(f"MCP返回了非JSON内容，长度: {len(text_content)}")
            return text_content
    
    except Exception as e:
        logger.error(f"写入文件异常: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}

def list_directory(path="."):
    """使用MCP Filesystem列出目录内容"""
    try:
        # 强制使用绝对路径指向桌面目录
        request_path = "C:\\Users\\Jason\\Desktop"  
        logger.info(f"使用MCP Filesystem列出目录内容（绝对路径）: {request_path}")
        
        # 准备请求体
        request_body = {
            "path": request_path
        }
        
        # 发送请求
        endpoint = f"{MCP_FILESYSTEM_URL}/list_directory"
        logger.info(f"发送请求到端点: {endpoint}")
        logger.info(f"请求体: {request_body}")
        
        try:
            response = requests.post(
                endpoint,
                json=request_body,
                timeout=30
            )
            
            logger.info(f"MCP Filesystem响应状态码: {response.status_code}")
            logger.info(f"MCP Filesystem响应头: {response.headers}")
            
            # 处理响应
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"MCP Filesystem错误响应: {error_text}")
                return {"error": f"MCP服务返回HTTP错误: {response.status_code} - {error_text[:100]}"}
            
            # 获取响应内容
            try:
                result = response.json()
                
                # 检查结果是否包含错误信息
                if isinstance(result, list) and len(result) == 1 and isinstance(result[0], str) and result[0].startswith("Error:"):
                    error_msg = result[0]
                    logger.error(f"MCP Filesystem返回错误: {error_msg}")
                    return {"error": error_msg}
                
                logger.info(f"成功解析JSON响应，获取到 {len(result) if isinstance(result, list) else '未知数量的'} 项")
                return result
            except ValueError as json_err:
                text_content = response.text
                logger.error(f"解析JSON失败: {str(json_err)}")
                logger.info(f"MCP返回了非JSON内容: {text_content[:200]}")
                return {"error": f"无法解析服务器响应: {str(json_err)}"}
        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f"连接错误: {str(conn_err)}")
            return {"error": f"无法连接到MCP服务: {str(conn_err)}"}
        except requests.exceptions.Timeout as timeout_err:
            logger.error(f"请求超时: {str(timeout_err)}")
            return {"error": f"请求MCP服务超时: {str(timeout_err)}"}
        except requests.exceptions.RequestException as req_err:
            logger.error(f"请求异常: {str(req_err)}")
            return {"error": f"请求MCP服务异常: {str(req_err)}"}
    
    except Exception as e:
        logger.error(f"列目录异常: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}

def search_files(path=".", pattern="*", exclude_patterns=None):
    """使用MCP Filesystem搜索文件"""
    try:
        logger.info(f"使用MCP Filesystem搜索文件，路径: {path}, 模式: {pattern}")
        
        # 准备请求体
        request_body = {
            "path": path,
            "pattern": pattern
        }
        
        if exclude_patterns:
            request_body["excludePatterns"] = exclude_patterns
        
        # 发送请求
        response = requests.post(
            f"{MCP_FILESYSTEM_URL}/search_files",
            json=request_body,
            timeout=30
        )
        
        logger.info(f"MCP Filesystem响应状态码: {response.status_code}")
        
        # 处理响应
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"MCP Filesystem错误响应: {error_text}")
            return {"error": f"MCP服务返回HTTP错误: {response.status_code} - {error_text[:100]}"}
        
        # 获取响应内容
        try:
            result = response.json()
            return result
        except ValueError:
            text_content = response.text
            logger.info(f"MCP返回了非JSON内容，长度: {len(text_content)}")
            return text_content
    
    except Exception as e:
        logger.error(f"搜索文件异常: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}

def get_file_info(path):
    """使用MCP Filesystem获取文件信息"""
    try:
        logger.info(f"使用MCP Filesystem获取文件信息: {path}")
        
        # 准备请求体
        request_body = {
            "path": path
        }
        
        # 发送请求
        response = requests.post(
            f"{MCP_FILESYSTEM_URL}/get_file_info",
            json=request_body,
            timeout=30
        )
        
        logger.info(f"MCP Filesystem响应状态码: {response.status_code}")
        
        # 处理响应
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"MCP Filesystem错误响应: {error_text}")
            return {"error": f"MCP服务返回HTTP错误: {response.status_code} - {error_text[:100]}"}
        
        # 获取响应内容
        try:
            result = response.json()
            return result
        except ValueError:
            text_content = response.text
            logger.info(f"MCP返回了非JSON内容，长度: {len(text_content)}")
            return text_content
    
    except Exception as e:
        logger.error(f"获取文件信息异常: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": str(e)} 