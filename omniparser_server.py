import os
os.environ['KMP_DUPLICATE_LIB_OK']='TRUE'
# 设置内存优化环境变量
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512'
import logging
import gc
import torch
import base64
import io
from PIL import Image
from flask import Flask, request, jsonify
from util.omniparser import Omniparser


# --- 初始化 Flask 应用 ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# --- 全局加载模型 ---
# 模型只在服务启动时加载一次，避免每次请求都重复加载，以保证高性能。
OMNIPARSER_INSTANCE = None


def initialize_parser():
    """加载并初始化 OmniParser 模型。"""
    global OMNIPARSER_INSTANCE
    if OMNIPARSER_INSTANCE is not None:
        return
    try:
        logging.info("正在初始化 OmniParser 实例...")
        config = {
            'som_model_path': 'weights/icon_detect/model.pt',
            'caption_model_name': 'florence2',
            'caption_model_path': 'weights/icon_caption_florence',
            'BOX_TRESHOLD': 0.05
        }
        OMNIPARSER_INSTANCE = Omniparser(config)
        logging.info("OmniParser 实例已成功初始化。")
    except Exception as e:
        logging.error(f"初始化 OmniParser 实例失败: {e}", exc_info=True)
        # 如果初始化失败，程序应该退出或进行明确的错误处理
        raise e


def validate_image(image_base64):
    """验证并预处理图像"""
    try:
        # 解码base64图像
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        
        # 转换为RGB格式
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 检查图像尺寸
        width, height = image.size
        if width < 10 or height < 10:
            raise ValueError(f"图像尺寸过小: {width}x{height}，最小尺寸为10x10")
        
        if width > 4096 or height > 4096:
            # 如果图像过大，进行缩放
            max_size = 1920
            if width > height:
                new_width = max_size
                new_height = int(height * max_size / width)
            else:
                new_height = max_size
                new_width = int(width * max_size / height)
            
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logging.info(f"图像已从 {width}x{height} 缩放到 {new_width}x{new_height}")
        
        # 重新编码为base64
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        validated_base64 = base64.b64encode(buffered.getvalue()).decode('ascii')
        
        return validated_base64, image.size
        
    except Exception as e:
        raise ValueError(f"图像验证失败: {e}")


def format_parsed_content_for_client(parsed_content_list):
    """
    将Omniparser的解析结果格式化为客户端期望的格式
    客户端期望从结果中提取text、caption、description等字段
    """
    if not parsed_content_list:
        logging.warning("format_parsed_content_for_client: 输入为空")
        return []
    
    logging.info(f"format_parsed_content_for_client: 处理 {len(parsed_content_list)} 个原始项目")
    
    formatted_content = []
    
    for i, item in enumerate(parsed_content_list):
        logging.debug(f"处理第 {i+1} 项: {type(item)} - {item}")
        
        # 确保每个item都是字典格式，并包含客户端期望的字段
        if isinstance(item, dict):
            formatted_item = {}
            has_content = False
            
            # 检查所有可能的文本字段
            text_fields = ['text', 'caption', 'description', 'label', 'content']
            for field in text_fields:
                if field in item and item[field]:
                    if not formatted_item.get('text'):  # 只设置第一个找到的文本字段
                        formatted_item['text'] = str(item[field]).strip()
                        has_content = True
                    # 保留原始字段
                    formatted_item[field] = item[field]
            
            # 保留坐标信息（如果有）
            coord_fields = ['bbox', 'coordinates', 'box', 'position']
            for field in coord_fields:
                if field in item:
                    formatted_item[field] = item[field]
            
            # 保留其他元数据
            meta_fields = ['confidence', 'type', 'category', 'label', 'id', 'class']
            for field in meta_fields:
                if field in item:
                    formatted_item[field] = item[field]
            
            # 只有当有实际内容时才添加
            if has_content or any(field in item for field in coord_fields + meta_fields):
                formatted_content.append(formatted_item)
                logging.debug(f"添加格式化项目: {formatted_item}")
            else:
                logging.debug(f"跳过空项目: {item}")
                
        elif isinstance(item, str) and item.strip():
            # 如果item是非空字符串，包装成字典
            formatted_item = {'text': item.strip()}
            formatted_content.append(formatted_item)
            logging.debug(f"添加字符串项目: {formatted_item}")
        else:
            logging.debug(f"跳过无效项目类型 {type(item)}: {item}")
    
    logging.info(f"format_parsed_content_for_client: 输出 {len(formatted_content)} 个格式化项目")
    return formatted_content


# --- 健康检查端点 ---
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    if OMNIPARSER_INSTANCE is None:
        return jsonify({
            "status": "unhealthy", 
            "message": "OmniParser 服务未就绪"
        }), 503
    
    return jsonify({
        "status": "healthy", 
        "message": "OmniParser 服务正常运行",
        "service": "omniparser",
        "version": "1.0"
    }), 200


# --- 简单的ping端点 ---
@app.route('/ping', methods=['GET'])
def ping():
    """简单的连通性测试"""
    return jsonify({"message": "pong"}), 200


# --- 定义主要API端点 ---
@app.route('/parse', methods=['POST'])
def parse_image_endpoint():
    """接收 base64 编码的图片，返回解析结果。"""
    if OMNIPARSER_INSTANCE is None:
        return jsonify({"error": "OmniParser 服务未就绪"}), 503

    data = request.json
    if not data or 'image_base64' not in data:
        return jsonify({"error": "请求体中缺少 'image_base64' 字段"}), 400

    try:
        # 验证和预处理图像
        validated_image_base64, image_size = validate_image(data['image_base64'])
        logging.info(f"处理图像尺寸: {image_size}")
        
        # 调用 OmniParser 的核心方法
        dino_labeled_img, parsed_content_list = OMNIPARSER_INSTANCE.parse(validated_image_base64)
        
        # 调试：打印原始解析结果
        logging.info(f"原始解析结果类型: {type(parsed_content_list)}")
        logging.info(f"原始解析结果长度: {len(parsed_content_list) if parsed_content_list else 0}")
        if parsed_content_list:
            logging.info(f"解析结果前3项示例: {parsed_content_list[:3]}")
        
        # 格式化解析结果为客户端期望的格式
        formatted_content = format_parsed_content_for_client(parsed_content_list)
        
        # 调试：打印格式化后的结果
        logging.info(f"格式化后结果类型: {type(formatted_content)}")
        logging.info(f"格式化后结果长度: {len(formatted_content) if formatted_content else 0}")
        if formatted_content:
            logging.info(f"格式化结果前3项示例: {formatted_content[:3]}")
        
        # 处理完后立即清理内存
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # 合并所有文本内容，为客户端提供统一的combined_text
        all_texts = []
        for item in formatted_content:
            if isinstance(item, dict) and 'text' in item and item['text']:
                all_texts.append(str(item['text']).strip())
        
        combined_text = " ".join(all_texts) if all_texts else ""
        
        # 返回客户端期望的格式
        result = formatted_content  # 直接返回列表，客户端会遍历处理
        
        # 如果没有解析到任何内容，返回包含基本信息的响应
        if not result:
            # 仍然返回一个包含基本信息的列表
            result = [{
                "text": "图像已处理，但未检测到文本内容",
                "type": "status_message",
                "image_size": image_size
            }]
            logging.warning("没有有效的解析内容，返回状态消息")
        
        logging.info(f"最终返回结果: {len(result)} 个元素，合并文本长度: {len(combined_text)}")
        logging.info(f"最终返回的JSON大小: {len(str(result))} 字符")
        
        return jsonify(result)
    
    except ValueError as e:
        # 图像验证错误
        logging.warning(f"图像验证失败: {e}")
        return jsonify({"error": str(e)}), 400
    
    except Exception as e:
        logging.error(f"处理图像时出错: {e}", exc_info=True)
        # 出错时也清理内存
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return jsonify({"error": f"服务器内部错误: {e}"}), 500


# --- 错误处理 ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "端点不存在"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "请求方法不被允许"}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "服务器内部错误"}), 500


# --- 启动服务 ---
if __name__ == '__main__':
    try:
        initialize_parser()  # 在启动Web服务前先加载模型
        logging.info("OmniParser 服务启动成功")
        logging.info("可用端点:")
        logging.info("  POST /parse - 图像解析")
        logging.info("  GET /health - 健康检查")
        logging.info("  GET /ping - 连通性测试")
        
        # 使用 0.0.0.0 使其可以被本机其他进程访问
        app.run(host='0.0.0.0', port=5111, debug=False)
    except Exception as e:
        logging.error(f"服务启动失败: {e}")
        exit(1) 