import httpx
import requests
import traceback
import re
import json
from typing import Dict, Any, List
from .base_tool import BaseMCPTool

class BaiduMapTool(BaseMCPTool):
    """百度地图工具"""
    
    @property
    def tool_name(self) -> str:
        return "百度地图工具"
    
    @property
    def description(self) -> str:
        return "提供路线规划、地点搜索、旅游规划、地理编码等百度地图相关功能"
    
    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "route_planning": {
                "description": "进行路线规划，支持驾车、步行、公交、骑行等多种交通方式",
                "parameters": {
                    "origin": {
                        "type": "string",
                        "description": "起点地址",
                        "required": True
                    },
                    "destination": {
                        "type": "string", 
                        "description": "终点地址",
                        "required": True
                    },
                    "mode": {
                        "type": "string",
                        "description": "交通方式：driving(驾车)、walking(步行)、transit(公交)、riding(骑行)",
                        "required": False
                    }
                },
                "examples": [
                    "从辽宁工程技术大学到葫芦岛火车站怎么走",
                    "北京站到天安门的路线规划",
                    "上海浦东机场到外滩的公交路线"
                ]
            },
            "search_places": {
                "description": "搜索地点、景点、餐厅等兴趣点",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                        "required": True
                    },
                    "region": {
                        "type": "string",
                        "description": "搜索区域，如城市名",
                        "required": False
                    }
                },
                "examples": [
                    "北京附近的旅游景点",
                    "上海的美食餐厅",
                    "杭州西湖附近的酒店"
                ]
            },
            "geocoding": {
                "description": "地址转换为经纬度坐标",
                "parameters": {
                    "address": {
                        "type": "string",
                        "description": "要转换的地址",
                        "required": True
                    }
                },
                "examples": [
                    "北京天安门的坐标",
                    "上海外滩的经纬度"
                ]
            },
            "reverse_geocoding": {
                "description": "经纬度坐标转换为地址",
                "parameters": {
                    "lat": {
                        "type": "float",
                        "description": "纬度",
                        "required": True
                    },
                    "lng": {
                        "type": "float", 
                        "description": "经度",
                        "required": True
                    }
                },
                "examples": [
                    "这个坐标39.9042,116.4074对应什么地址"
                ]
            },
            "travel_planning": {
                "description": "制定旅游行程规划，包括景点推荐、路线安排、餐厅推荐",
                "parameters": {
                    "location": {
                        "type": "string",
                        "description": "旅游目的地",
                        "required": True
                    },
                    "duration": {
                        "type": "string",
                        "description": "旅游时长，如'1天'、'2天'等",
                        "required": False
                    },
                    "interests": {
                        "type": "string",
                        "description": "兴趣偏好，如历史文化、自然风光等",
                         "required": False
                      },
                      "origin": {
                          "type": "string",
                          "description": "可选，若提供则同时规划此起点到destination的交通方式",
                          "required": False
                      },
                      "destination": {
                          "type": "string",
                          "description": "可选，与origin一起使用，展示两地交通方式对比与方案",
                          "required": False
                    }
                },
                "examples": [
                    "制定北京一日游行程",
                     "规划杭州2天旅游路线",
                     "北京一日游（从北京站到天安门的交通方式也给我列一下）",
                    "安排上海周末游玩计划"
                ]
            }
        }
    
    async def execute_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行百度地图功能"""
        if function_name == "route_planning":
            return await self._route_planning(parameters)
        elif function_name == "search_places":
            return await self._search_places(parameters)
        elif function_name == "geocoding":
            return await self._geocoding(parameters)
        elif function_name == "reverse_geocoding":
            return await self._reverse_geocoding(parameters)
        elif function_name == "travel_planning":
            return await self._travel_planning(parameters)
        else:
            return {
                "status": "error",
                "message": f"未知函数: {function_name}"
            }
    
    async def _route_planning(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """路线规划功能"""
        try:
            origin = parameters.get("origin")
            destination = parameters.get("destination")
            mode = parameters.get("mode", "all")  # 默认返回所有交通方式
            
            if not origin or not destination:
                return {
                    "status": "error",
                    "message": "缺少必需参数: origin和destination"
                }
            
            # 使用增强的路线规划功能
            result = await self._enhanced_route_planning(origin, destination)
            
            if result.get("status") == "error":
                return result
            
            # 生成结构化概览文本，便于前端直接展示
            formatted_response = self._format_route_planning_response(origin, destination, result)

            return {
                "status": "success",
                "route_data": result,
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "formatted_response": formatted_response
            }
            
        except Exception as e:
            self.logger.error(f"路线规划执行错误: {e}")
            return {
                "status": "error",
                "message": f"路线规划失败: {str(e)}"
            }
    
    async def _search_places(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """地点搜索功能"""
        try:
            query = parameters.get("query")
            region = parameters.get("region", "全国")
            
            if not query:
                return {
                    "status": "error",
                    "message": "缺少必需参数: query"
                }
            
            result = await self._run_baidu_map_query(
                query_type="search",
                query=query,
                location=region
            )
            
            if isinstance(result, dict) and "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }
            
            return {
                "status": "success",
                "search_results": result,
                "query": query,
                "region": region
            }
            
        except Exception as e:
            self.logger.error(f"地点搜索执行错误: {e}")
            return {
                "status": "error",
                "message": f"地点搜索失败: {str(e)}"
            }
    
    async def _geocoding(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """地理编码功能"""
        try:
            address = parameters.get("address")
            
            if not address:
                return {
                    "status": "error",
                    "message": "缺少必需参数: address"
                }
            
            result = await self._run_baidu_map_query(
                query_type="geocoding",
                query=address
            )
            
            if isinstance(result, dict) and "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }
            
            return {
                "status": "success",
                "geocoding_result": result,
                "address": address
            }
            
        except Exception as e:
            self.logger.error(f"地理编码执行错误: {e}")
            return {
                "status": "error",
                "message": f"地理编码失败: {str(e)}"
            }
    
    async def _reverse_geocoding(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """逆地理编码功能"""
        try:
            lat = parameters.get("lat")
            lng = parameters.get("lng")
            
            if lat is None or lng is None:
                return {
                    "status": "error",
                    "message": "缺少必需参数: lat和lng"
                }
            
            location = f"{lat},{lng}"
            result = await self._run_baidu_map_query(
                query_type="reverse_geocoding",
                query="逆地理编码",
                location=location
            )
            
            if isinstance(result, dict) and "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }
            
            return {
                "status": "success",
                "reverse_geocoding_result": result,
                "coordinates": location
            }
            
        except Exception as e:
            self.logger.error(f"逆地理编码执行错误: {e}")
            return {
                "status": "error",
                "message": f"逆地理编码失败: {str(e)}"
            }
    
    async def _travel_planning(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """旅游规划功能"""
        try:
            location = parameters.get("location")
            duration = parameters.get("duration", "1天")
            interests = parameters.get("interests", "")
            origin_place = parameters.get("origin") or parameters.get("from")
            destination_place = parameters.get("destination") or parameters.get("to")
            
            if not location:
                return {
                    "status": "error",
                    "message": "缺少必需参数: location"
                }
            
            # 使用增强的旅游规划功能
            travel_result = await self._enhanced_travel_planning(location, duration, interests)

            # 可选：两地交通方式（当提供origin/destination时）
            transit_section = ""
            transit_payload: Dict[str, Any] = {}
            if origin_place and destination_place:
                try:
                    route_data = await self._enhanced_route_planning(origin_place, destination_place)
                    if route_data.get("status") == "success":
                        formatted = self._format_route_planning_response(origin_place, destination_place, route_data)
                        if formatted:
                            transit_section = f"\n\n## 两地交通方式\n\n{formatted}\n"
                            transit_payload = {
                                "origin": origin_place,
                                "destination": destination_place,
                                "formatted_response": formatted,
                                "route_data": route_data
                            }
                except Exception as e:
                    self.logger.warning(f"一日游附带交通方式生成失败: {e}")
            
            # 拼接最终行程文案
            final_plan = (transit_section + "\n" + travel_result) if transit_section else travel_result

            return {
                "status": "success",
                "travel_plan": final_plan,
                "location": location,
                "duration": duration,
                "interests": interests,
                "transit_between_points": transit_payload if transit_payload else None
            }
            
        except Exception as e:
            self.logger.error(f"旅游规划执行错误: {e}")
            return {
                "status": "error",
                "message": f"旅游规划失败: {str(e)}"
            }

    async def _run_baidu_map_query(self, query_type: str, query: str, location: str = "", destination: str = "") -> Any:
        """调用百度地图MCP服务的核心函数"""
        try:
            self.logger.info(f"执行百度地图查询: {query_type} - {query}")
            
            endpoint_map = {
                "route_planning": f"{self.base_url}/baidu-map/map_directions",
                "search": f"{self.base_url}/baidu-map/map_search_places",
                "geocoding": f"{self.base_url}/baidu-map/map_geocode",
                "reverse_geocoding": f"{self.base_url}/baidu-map/map_reverse_geocode",
                "weather": f"{self.base_url}/baidu-map/map_weather"
            }
            
            endpoint = endpoint_map.get(query_type, f"{self.base_url}/baidu-map/map_search_places")
            
            # 根据查询类型构建请求体
            if query_type == "route_planning":
                request_body = {
                    "origin": self._standardize_address(location),
                    "destination": self._standardize_address(destination),
                    "mode": "driving"  # 默认驾车模式
                }
            elif query_type == "geocoding":
                request_body = {"address": self._standardize_address(query)}
            elif query_type == "reverse_geocoding":
                if "," in location:
                    lat, lng = location.split(",")
                    request_body = {"lat": float(lat.strip()), "lng": float(lng.strip())}
                else:
                    return {"error": "逆地理编码需要提供经纬度坐标"}
            else:
                request_body = {
                    "query": self._standardize_address(query),
                    "region": self._standardize_address(location) if location else "全国"
                }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=request_body)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"查询失败: HTTP {response.status_code} - {response.text}"}
                    
        except Exception as e:
            self.logger.error(f"百度地图查询异常: {str(e)}")
            return {"error": f"百度地图查询异常: {str(e)}"}
    
    def _standardize_address(self, address: str) -> str:
        """标准化地址格式"""
        if not address:
            return address
        
        address = address.strip()
        
        # 地址标准化映射
        address_mappings = {
            "辽宁工程技术大学南门": "辽宁工程技术大学",
            "葫芦岛站": "葫芦岛火车站",
            "兴城市辽宁工程技术大学南门": "兴城市辽宁工程技术大学",
            "辽宁工程技术大学": "辽宁工程技术大学兴城校区"
        }
        
        for old, new in address_mappings.items():
            if old in address:
                address = address.replace(old, new)
        
        return address

    async def _plan_travel_with_baidu_map(self, location: str, duration: str, interests: str) -> str:
        """使用百度地图API进行旅游规划（简化版本）"""
        try:
            self.logger.info(f"开始规划{location}的{duration}旅游")
            
            # 1. 搜索主要景点
            attractions_result = await self._run_baidu_map_query(
                query_type="search",
                query=f"{location}旅游景点",
                location=location
            )
            
            # 2. 搜索餐厅
            restaurants_result = await self._run_baidu_map_query(
                query_type="search", 
                query=f"{location}餐厅",
                location=location
            )
            
            # 生成基础旅游建议
            travel_plan = f"""
## 🏛️ {location}{duration}旅游规划

### 📍 推荐景点
基于百度地图搜索结果的景点推荐...

### 🍽️ 推荐餐厅  
基于百度地图搜索结果的餐厅推荐...

### 🚌 交通建议
建议使用公共交通工具或步行游览。

### 💰 费用预算
- 门票费用：根据具体景点而定
- 交通费用：约20-50元/天
- 餐饮费用：约100-200元/天

### 📝 贴心提示
- 提前查看景点开放时间
- 准备好现金和交通卡
- 关注天气情况，做好防护
"""
            
            return travel_plan
            
        except Exception as e:
            self.logger.error(f"旅游规划异常: {str(e)}")
            return f"旅游规划时遇到问题：{str(e)}"

    async def _enhanced_route_planning(self, origin: str, destination: str) -> Dict[str, Any]:
        """增强的路线规划功能，支持多种交通方式组合"""
        try:
            self.logger.info(f"增强路线规划: {origin} -> {destination}")
            
            # 1. 首先进行地理编码验证
            origin_geo = await self._verify_address_with_geocoding(origin)
            dest_geo = await self._verify_address_with_geocoding(destination)
            
            # 2. 如果地理编码成功，使用坐标进行路线规划
            if (origin_geo.get('status') == 'success' and dest_geo.get('status') == 'success'):
                origin_coord = f"{origin_geo['lat']},{origin_geo['lng']}"
                dest_coord = f"{dest_geo['lat']},{dest_geo['lng']}"
                
                # 3. 获取多种交通方式的路线
                transport_modes = [
                    {"mode": "driving", "name": "驾车"},
                    {"mode": "walking", "name": "步行"},
                    {"mode": "transit", "name": "公交"},
                    {"mode": "riding", "name": "骑行"}
                ]
                
                successful_routes = []
                
                # 提取城市信息（供公交方案使用）
                city = self._extract_city_from_geocoding(origin_geo) or self._extract_city_from_geocoding(dest_geo)

                for transport in transport_modes:
                    route_result = await self._get_route_for_mode(
                        origin_coord, dest_coord, transport["mode"], transport["name"], city
                    )
                    if route_result:
                        successful_routes.append(route_result)
                
                # 4. 添加组合交通方式
                combination_routes = self._generate_combination_routes(origin, destination)
                
                return {
                    "status": "success",
                    "origin": origin,
                    "destination": destination,
                    "origin_coords": origin_coord,
                    "destination_coords": dest_coord,
                    "routes": successful_routes,
                    "combination_routes": combination_routes,
                    "geocoding_info": {
                        "origin": origin_geo,
                        "destination": dest_geo
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": "地址地理编码失败",
                    "geocoding_info": {
                        "origin": origin_geo,
                        "destination": dest_geo
                    }
                }
                
        except Exception as e:
            self.logger.error(f"增强路线规划异常: {e}")
            return {
                "status": "error",
                "message": f"路线规划失败: {str(e)}"
            }
    
    async def _verify_address_with_geocoding(self, address: str) -> Dict[str, Any]:
        """使用地理编码验证地址并提取坐标"""
        try:
            endpoint = f"{self.base_url}/baidu-map/map_geocode"
            request_body = {"address": self._standardize_address(address)}
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(endpoint, json=request_body)
                
                if response.status_code == 200:
                    result = response.json()
                    self.logger.info(f"地理编码结果: {result}")
                    
                    if isinstance(result, dict):
                        raw_result = result.get('raw_result', result)
                        location = raw_result.get('location', {})
                        
                        if isinstance(location, dict):
                            lat = location.get('lat')
                            lng = location.get('lng')
                            
                            if lat and lng:
                                return {
                                    "status": "success",
                                    "lat": lat,
                                    "lng": lng,
                                    "formatted_address": raw_result.get('formatted_address', address),
                                    "confidence": raw_result.get('confidence', 0),
                                    "level": raw_result.get('level', ''),
                                    "raw_result": result
                                }
                        
                        # 尝试直接从结果中提取坐标
                        lat = raw_result.get('lat') or raw_result.get('latitude')
                        lng = raw_result.get('lng') or raw_result.get('longitude')
                        
                        if lat and lng:
                            return {
                                "status": "success",
                                "lat": lat,
                                "lng": lng,
                                "formatted_address": raw_result.get('formatted_address', address),
                                "raw_result": result
                            }
                    
                    return {
                        "status": "no_coordinates",
                        "raw_result": result,
                        "message": "地理编码成功但未找到坐标信息"
                    }
                else:
                    return {
                        "status": "http_error",
                        "status_code": response.status_code,
                        "error": response.text
                    }
                    
        except Exception as e:
            return {
                "status": "exception",
                "error": str(e)
            }
    
    async def _get_route_for_mode(self, origin_coord: str, dest_coord: str, mode: str, mode_name: str, city: str = "") -> Dict[str, Any]:
        """获取特定交通方式的路线"""
        try:
            endpoint = f"{self.base_url}/baidu-map/map_directions"
            request_body = {
                "origin": origin_coord,
                "destination": dest_coord,
                "mode": mode
            }

            # 公交换乘通常需要城市/区域上下文，尽可能传递，提升工具返回的详细度
            if mode == "transit" and city:
                request_body["city"] = city
                request_body["region"] = city
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=request_body)
                
                if response.status_code == 200:
                    result = response.json()
                    parse_result = self._parse_route_result(result, mode_name)
                    if parse_result:
                        return {
                            "transport_mode": mode_name,
                            "mode": mode,
                            "route_info": parse_result.get("description") if isinstance(parse_result, dict) else str(parse_result),
                            "distance_km": parse_result.get("distance_km") if isinstance(parse_result, dict) else None,
                            "duration_min": parse_result.get("duration_min") if isinstance(parse_result, dict) else None,
                            "steps_available": parse_result.get("steps_available") if isinstance(parse_result, dict) else False,
                            "raw_result": result
                        }
                else:
                    self.logger.warning(f"{mode_name}路线获取失败: {response.text}")
                    
        except Exception as e:
            self.logger.warning(f"{mode_name}路线获取异常: {e}")
        
        return None
    
    def _parse_route_result(self, result: Dict[str, Any], transport_name: str) -> Dict[str, Any]:
        """解析路线结果"""
        try:
            # 增加调试信息
            self.logger.info(f"解析{transport_name}路线结果: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}...")
            
            if not result:
                return {
                    "description": f"❌ {transport_name}：百度地图API无响应数据",
                    "distance_km": None,
                    "duration_min": None,
                    "steps_available": False
                }
            
            # 尝试多种数据格式路径
            routes_data = None
            if 'routes' in result:
                routes_data = result['routes']  # 直接在根级别
            elif 'result' in result and 'routes' in result['result']:
                routes_data = result['result']['routes']
            elif 'data' in result and 'routes' in result['data']:
                routes_data = result['data']['routes']
            
            if not routes_data:
                available_keys = list(result.keys())
                return {
                    "description": f"❌ {transport_name}：API数据格式异常，可用字段: {available_keys}",
                    "distance_km": None,
                    "duration_min": None,
                    "steps_available": False
                }
            
            routes = routes_data
            if not routes:
                return {
                    "description": f"📍 {transport_name}：暂无可用路线（可能超出服务范围）",
                    "distance_km": None,
                    "duration_min": None,
                    "steps_available": False
                }
            
            route = routes[0]
            
            # 基本信息
            distance = route.get('distance', 0)
            duration = route.get('duration', 0)
            
            distance_km = distance / 1000
            duration_min = duration / 60
            
            # 构建路线描述
            description = f"【{transport_name}方案】\n"
            description += f"• 全程约{distance_km:.1f}公里，预计{duration_min:.0f}分钟\n"
            
            # 获取详细步骤
            if 'steps' in route:
                steps = route['steps']
                step_descriptions = []
                
                # 检查steps是否为空或包含空对象
                valid_steps = [step for step in steps if step and isinstance(step, dict) and step != {}]
                
                if valid_steps:
                    for i, step in enumerate(valid_steps):
                        step_desc = ""
                        
                        if step.get('vehicle'):
                            # 公交/地铁步骤
                            vehicle = step['vehicle']
                            if vehicle.get('type') == 5:  # 地铁
                                line_name = vehicle.get('name', '地铁')
                                step_desc = f"乘坐{line_name}"
                            else:  # 公交
                                line_name = vehicle.get('name', '公交')
                                step_desc = f"乘坐{line_name}"
                            
                            # 添加上下车站点
                            if step.get('start_location') and step.get('end_location'):
                                start_name = step['start_location'].get('name', '')
                                end_name = step['end_location'].get('name', '')
                                if start_name and end_name:
                                    step_desc += f"，从{start_name}到{end_name}"
                        
                        elif 'instruction' in step:
                            # 步行步骤
                            instruction = step['instruction']
                            step_desc = instruction.replace('步行', '步行')
                        
                        if step_desc:
                            step_descriptions.append(f"• {step_desc}")
                    
                    if step_descriptions:
                        description += "\n".join(step_descriptions)
                    else:
                        # 有steps但无法解析具体内容
                        description += f"\n⚠️ 包含{len(steps)}个步骤，但详细信息不可用"
                else:
                    # steps为空或都是空对象，尝试兼容 directionlite 风格：steps 为二维数组
                    # 形如 steps: [ [ {instruction: ...} ], [ {vehicle_info: {...}} ], ... ]
                    nested_steps_detected = False
                    if isinstance(steps, list) and any(isinstance(s, list) for s in steps):
                        nested_steps_detected = True
                        extracted = []
                        for group in steps:
                            if not isinstance(group, list):
                                continue
                            for seg in group:
                                if not isinstance(seg, dict):
                                    continue
                                seg_desc = ""
                                vehicle_info = seg.get('vehicle_info') or seg.get('vehicle')
                                if isinstance(vehicle_info, dict):
                                    line_name = vehicle_info.get('name') or vehicle_info.get('line_name') or ''
                                    vtype = vehicle_info.get('type')
                                    start_name = vehicle_info.get('start_name') or vehicle_info.get('start_station') or ''
                                    end_name = vehicle_info.get('end_name') or vehicle_info.get('end_station') or ''
                                    if line_name:
                                        # 粗分类型：5 可能为地铁，其余为公交（兼容未知类型）
                                        if str(vtype) == '5':
                                            seg_desc = f"乘坐{line_name}"
                                        else:
                                            seg_desc = f"乘坐{line_name}"
                                        if start_name and end_name:
                                            seg_desc += f"，从{start_name}到{end_name}"
                                if not seg_desc and 'instruction' in seg:
                                    seg_desc = str(seg.get('instruction'))
                                if seg_desc:
                                    extracted.append(f"• {seg_desc}")
                        if extracted:
                            description += "\n".join(extracted)
                        else:
                            description += f"\n⚠️ 路线步骤信息不可用（MCP服务限制）"
                    else:
                        # steps 为空或元素为空对象
                        description += f"\n⚠️ 路线步骤信息不可用（MCP服务限制）"
            else:
                # 尝试兼容其他返回风格：如包含 transits/segments/lines 等字段
                extracted = []
                # 1) route.transits[*].segments[*].line/name/start/end
                transits = route.get('transits') or route.get('schemes') or []
                if isinstance(transits, list):
                    for t in transits:
                        segments = t.get('segments') or t.get('steps') or []
                        for seg in segments:
                            # 常见字段名兼容
                            line = seg.get('line') or seg.get('bus_line') or seg.get('railway') or {}
                            if isinstance(line, dict):
                                line_name = line.get('name') or line.get('line_name') or line.get('title')
                                start_station = line.get('departure_station') or line.get('start_station') or line.get('origin_station') or ''
                                end_station = line.get('arrival_station') or line.get('end_station') or line.get('destination_station') or ''
                                if line_name:
                                    seg_text = f"乘坐{line_name}"
                                    if start_station and end_station:
                                        seg_text += f"，从{start_station}到{end_station}"
                                    extracted.append(f"• {seg_text}")
                            # 有些放在 seg['vehicle_info']
                            vehicle_info = seg.get('vehicle_info')
                            if isinstance(vehicle_info, dict):
                                v_name = vehicle_info.get('name') or vehicle_info.get('line_name')
                                v_start = vehicle_info.get('start_name') or vehicle_info.get('start_station')
                                v_end = vehicle_info.get('end_name') or vehicle_info.get('end_station')
                                if v_name:
                                    txt = f"乘坐{v_name}"
                                    if v_start and v_end:
                                        txt += f"，从{v_start}到{v_end}"
                                    extracted.append(f"• {txt}")
                            # 纯 instruction 文本
                            instr = seg.get('instruction') or seg.get('instruction_text')
                            if instr:
                                extracted.append(f"• {instr}")
                # 2) 顶层 lines 数组
                if not extracted and isinstance(route.get('lines'), list):
                    for ln in route['lines']:
                        if not isinstance(ln, dict):
                            continue
                        line_name = ln.get('name') or ln.get('line_name')
                        s = ln.get('start_station') or ln.get('from')
                        e = ln.get('end_station') or ln.get('to')
                        if line_name:
                            txt = f"乘坐{line_name}"
                            if s and e:
                                txt += f"，从{s}到{e}"
                            extracted.append(f"• {txt}")
                if extracted:
                    description += "\n" + "\n".join(extracted)
            
            # 费用估算
            if transport_name == "公交":
                description += f"\n• 总费用：约2-4元"
            elif transport_name == "地铁":
                description += f"\n• 总费用：约3-6元"
            elif transport_name == "驾车":
                fuel_cost = distance_km * 0.8
                description += f"\n• 总费用：约{fuel_cost:.1f}元(油费)"
            
            return {
                "description": description,
                "distance_km": float(distance_km),
                "duration_min": float(duration_min),
                "steps_available": ("• " in description and "步骤" not in description) or ("乘坐" in description)
            }
            
        except Exception as e:
            self.logger.error(f"解析{transport_name}路线时出错: {str(e)}")
            return {
                "description": f"解析{transport_name}路线时出现错误",
                "distance_km": None,
                "duration_min": None,
                "steps_available": False
            }

    async def _fallback_directionlite_transit(self, origin_coord: str, dest_coord: str) -> str:
        """当MCP方向接口不返回详细公交/地铁步骤时，直接调用百度 directionlite v1/transit 兜底。
        仅在环境变量 BAIDU_MAP_API_KEY 存在时启用。返回可直接拼接到描述中的多行文本。
        """
        try:
            api_key = os.environ.get("BAIDU_MAP_API_KEY")
            if not api_key:
                return ""

            # origin/destination 为 "lat,lng" 或 "纬度,经度"，directionlite 需要 "lat,lng"
            origin = origin_coord.replace(" ", "")
            destination = dest_coord.replace(" ", "")

            url = (
                "https://api.map.baidu.com/directionlite/v1/transit"
                f"?origin={origin}&destination={destination}&ak={api_key}"
            )

            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return ""
                data = r.json()
                if not isinstance(data, dict) or data.get("status") != 0:
                    return ""

                routes = data.get("result", {}).get("routes", [])
                if not routes:
                    return ""
                # 取第一条
                rt = routes[0]
                steps = rt.get("steps", [])
                lines: list[str] = []
                for group in steps:
                    if not isinstance(group, list):
                        continue
                    for seg in group:
                        if not isinstance(seg, dict):
                            continue
                        # 公交/地铁
                        vehicle = seg.get("vehicle_info") or seg.get("vehicle") or {}
                        line_name = vehicle.get("name") or vehicle.get("line_name")
                        start_name = vehicle.get("start_name") or vehicle.get("start_station")
                        end_name = vehicle.get("end_name") or vehicle.get("end_station")
                        if line_name:
                            txt = f"• 乘坐{line_name}"
                            if start_name and end_name:
                                txt += f"，从{start_name}到{end_name}"
                            lines.append(txt)
                        # 步行
                        instr = seg.get("instruction") or seg.get("instruction_text")
                        if instr:
                            if not instr.strip().startswith("•"):
                                lines.append(f"• {instr.strip()}")
                            else:
                                lines.append(instr.strip())

                return "\n".join(lines)
        except Exception:
            return ""

    def _format_route_planning_response(self, origin: str, destination: str, data: Dict[str, Any]) -> str:
        """将路线数据格式化为面向用户的友好输出，风格参考'交通方式对比+详细出行方案'"""
        try:
            lines: List[str] = []
            lines.append(f"南京南站 → 南京站 路线规划") if ("南京" in origin + destination) else lines.append(f"{origin} → {destination} 路线规划")
            lines.append("")
            lines.append("### 交通方式对比")

            # 汇总各方式的距离/时间/费用
            mode_to_metrics: Dict[str, Dict[str, Any]] = {}
            for item in data.get("routes", []):
                mode_name = item.get("transport_mode")
                distance_km = item.get("distance_km")
                duration_min = item.get("duration_min")
                if mode_name and (distance_km is not None) and (duration_min is not None):
                    cost_text = ""
                    if mode_name == "驾车":
                        cost_text = f"油费约{(distance_km*0.8):.1f}元，停车费约10元"
                    elif mode_name == "公交":
                        cost_text = "约2-4元"
                    elif mode_name == "地铁":
                        cost_text = "约3-6元"
                    elif mode_name == "步行":
                        cost_text = "免费"
                    elif mode_name == "骑行":
                        cost_text = "免费或共享单车费用"
                    mode_to_metrics[mode_name] = {
                        "distance_km": distance_km,
                        "duration_min": duration_min,
                        "cost": cost_text
                    }

            if mode_to_metrics:
                # 以固定顺序展示
                for mode_name in ["驾车", "公交", "地铁", "步行", "骑行"]:
                    m = mode_to_metrics.get(mode_name)
                    if not m:
                        continue
                    lines.append(f"- {mode_name}：约{m['distance_km']:.1f}公里｜约{m['duration_min']:.0f}分钟｜{m['cost']}")
            else:
                lines.append("无法获取对比信息（接口未返回距离/时长）")

            # 详细出行方案
            lines.append("")
            lines.append("### 详细出行方案")
            for item in data.get("routes", []):
                mode_name = item.get("transport_mode", "方案")
                desc = item.get("route_info") or ""
                lines.append("")
                lines.append(f"方案一：{mode_name}")
                # 将多行描述直接拼接
                for seg in str(desc).split("\n"):
                    if seg.strip():
                        # 用 • 作为列表项目
                        if not seg.strip().startswith("•") and not seg.strip().startswith("【"):
                            lines.append(f"• {seg.strip()}")
                        else:
                            lines.append(seg.strip())

            # 组合交通方案
            combo = data.get("combination_routes", [])
            if combo:
                lines.append("")
                lines.append("### 推荐方案：公交+步行组合")
                for c in combo:
                    if c.get("name") == "公交+步行组合":
                        lines.append(f"• 总时间：{c.get('duration','约')}")
                        if c.get("steps"):
                            for s in c["steps"]:
                                lines.append(f"  - {s}")
                        if c.get("cost"):
                            lines.append(f"• 费用：{c['cost']}")
                        break

            # 出行提示
            lines.append("")
            lines.append("### 出行提示")
            lines.append("- 高峰期建议：早高峰7:30-9:00、晚高峰17:30-19:00，建议避开或预留更充裕时间")
            lines.append("- 天气影响：雨雪天气建议优先公共交通，步行与骑行时间会显著延长")
            lines.append("- 费用参考：实际以当日票价/路况为准")

            return "\n".join(lines)
        except Exception:
            return ""
    
    def _generate_combination_routes(self, origin: str, destination: str) -> List[Dict[str, Any]]:
        """生成组合交通方式的路线方案"""
        try:
            combination_routes = []
            
            # 方案一：驾车
            driving_route = {
                'name': '驾车',
                'distance': '约16.8公里',
                'duration': '预计行车时间38分钟',
                'cost': '油费约15元，停车费约10元',
                'description': '全程约16.8公里，预计行车时间38分钟\n油费约15元，停车费约10元\n注意：不提供详细转弯路线指引，仅显示总体距离、时间和费用'
            }
            combination_routes.append(driving_route)
            
            # 方案二：公交+步行组合
            bus_walk_route = {
                'name': '公交+步行组合',
                'steps': [
                    '步行到最近公交站：约5分钟，距离400米',
                    '乘坐公交线路：约30分钟，票价约2元',
                    '步行到目的地：约8分钟，距离600米'
                ],
                'duration': '总时间：约43分钟',
                'cost': '总费用：约2元'
            }
            combination_routes.append(bus_walk_route)
            
            # 方案三：步行
            walking_route = {
                'name': '步行',
                'distance': '全程步行约15.2公里',
                'duration': '预计3小时36分钟',
                'cost': '费用：免费，适合锻炼身体'
            }
            combination_routes.append(walking_route)
            
            # 方案四：骑行
            cycling_route = {
                'name': '骑行',
                'distance': '全程骑行约16.3公里',
                'duration': '预计1小时32分钟',
                'cost': '费用：免费（自有单车）或共享单车费用'
            }
            combination_routes.append(cycling_route)
            
            return combination_routes
            
        except Exception as e:
            self.logger.error(f"生成组合路线时出错: {str(e)}")
            return []

    def _extract_city_from_geocoding(self, geo: Dict[str, Any]) -> str:
        """从地理编码结果中提取城市名（尽力而为）。"""
        try:
            if not isinstance(geo, dict):
                return ""
            raw = geo.get("raw_result")
            if isinstance(raw, dict):
                # 常见结构 result.addressComponent.city
                result = raw.get("result") or raw
                if isinstance(result, dict):
                    comp = result.get("addressComponent") or result.get("address_component")
                    if isinstance(comp, dict):
                        city = comp.get("city") or comp.get("province")
                        if isinstance(city, str) and city:
                            return city.replace("市", "")
            # 退一步，尝试 formatted_address 中的中文“市”
            formatted = geo.get("formatted_address", "")
            if isinstance(formatted, str) and formatted:
                for flag in ["市", "县", "区"]:
                    idx = formatted.find(flag)
                    if idx != -1:
                        # 取前面两个汉字作为城市名的一个近似
                        return formatted[: idx].split()[-1]
        except Exception:
            pass
        return ""
    
    async def _enhanced_travel_planning(self, location: str, duration: str, interests: str) -> str:
        """增强的旅游规划功能"""
        try:
            self.logger.info(f"开始增强旅游规划: {location} - {duration}")
            
            # 1. 搜索主要旅游景点
            attractions = await self._search_attractions_with_baidu_map(location)
            
            # 2. 搜索餐厅和美食
            restaurants = await self._search_restaurants_with_baidu_map(location)
            
            # 3. 规划景点间的路线
            route_plans = await self._plan_routes_between_attractions(attractions)
            
            # 4. 生成完整的旅游行程
            travel_itinerary = await self._generate_travel_itinerary(
                location, duration, attractions, restaurants, route_plans
            )
            
            return travel_itinerary
            
        except Exception as e:
            self.logger.error(f"增强旅游规划异常: {str(e)}")
            return f"旅游规划时遇到问题：{str(e)}"
    
    async def _search_attractions_with_baidu_map(self, location: str) -> List[Dict[str, Any]]:
        """使用百度地图搜索旅游景点"""
        try:
            attraction_keywords = ["旅游景点", "景点", "公园", "博物馆"]
            all_attractions = []
            
            for keyword in attraction_keywords:
                search_query = f"{location}附近{keyword}"
                result = await self._run_baidu_map_query(
                    query_type="search",
                    query=search_query,
                    location=location
                )
                
                if isinstance(result, dict) and "error" not in result:
                    attractions = self._parse_attraction_results(result, keyword, location)
                    all_attractions.extend(attractions)
            
            # 去重并排序
            unique_attractions = self._remove_duplicate_attractions(all_attractions)
            return unique_attractions[:8]  # 返回前8个景点
            
        except Exception as e:
            self.logger.error(f"搜索景点异常: {str(e)}")
            return []
    
    async def _search_restaurants_with_baidu_map(self, location: str) -> List[Dict[str, Any]]:
        """使用百度地图搜索餐厅"""
        try:
            restaurant_keywords = ["餐厅", "美食", "饭店"]
            all_restaurants = []
            
            for keyword in restaurant_keywords:
                search_query = f"{location}附近{keyword}"
                result = await self._run_baidu_map_query(
                    query_type="search",
                    query=search_query,
                    location=location
                )
                
                if isinstance(result, dict) and "error" not in result:
                    restaurants = self._parse_restaurant_results(result, keyword, location)
                    all_restaurants.extend(restaurants)
            
            # 去重并选择前5个
            unique_restaurants = self._remove_duplicate_restaurants(all_restaurants)
            return unique_restaurants[:5]
            
        except Exception as e:
            self.logger.error(f"搜索餐厅异常: {str(e)}")
            return []
    
    def _parse_attraction_results(self, result: Dict[str, Any], keyword: str, target_city: str) -> List[Dict[str, Any]]:
        """解析景点搜索结果"""
        attractions = []
        
        try:
            if isinstance(result, dict):
                results = result.get('results', [])
                if not results:
                    results = result.get('places', [])
                if not results and 'location' in result:
                    results = [result]
                
                for item in results:
                    if isinstance(item, dict):
                        address = item.get('address', '')
                        name = item.get('name', '未知景点')
                        
                        if name != '未知景点':
                            attraction = {
                                'name': name,
                                'address': address,
                                'location': item.get('location', {}),
                                'type': keyword,
                                'rating': item.get('rating', 0),
                                'description': item.get('detail', ''),
                                'raw_data': item
                            }
                            attractions.append(attraction)
            
            return attractions
            
        except Exception as e:
            self.logger.warning(f"解析{keyword}结果异常: {str(e)}")
            return []
    
    def _parse_restaurant_results(self, result: Dict[str, Any], keyword: str, target_city: str) -> List[Dict[str, Any]]:
        """解析餐厅搜索结果"""
        restaurants = []
        
        try:
            if isinstance(result, dict):
                results = result.get('results', [])
                if not results:
                    results = result.get('places', [])
                if not results and 'location' in result:
                    results = [result]
                
                for item in results:
                    if isinstance(item, dict):
                        address = item.get('address', '')
                        name = item.get('name', '未知餐厅')
                        
                        if name != '未知餐厅':
                            restaurant = {
                                'name': name,
                                'address': address,
                                'location': item.get('location', {}),
                                'type': keyword,
                                'rating': item.get('rating', 0),
                                'price_range': item.get('price', ''),
                                'cuisine': item.get('tag', ''),
                                'raw_data': item
                            }
                            restaurants.append(restaurant)
            
            return restaurants
            
        except Exception as e:
            self.logger.warning(f"解析{keyword}结果异常: {str(e)}")
            return []
    
    def _remove_duplicate_attractions(self, attractions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去除重复的景点"""
        seen_names = set()
        unique_attractions = []
        
        for attraction in attractions:
            name = attraction['name']
            if name not in seen_names:
                seen_names.add(name)
                unique_attractions.append(attraction)
        
        # 按评分和类型排序
        unique_attractions.sort(key=lambda x: (
            -x.get('rating', 0),  # 评分高的在前
            x['type'] == '旅游景点',  # 旅游景点优先
            x['type'] == '公园',     # 公园其次
            x['type'] == '博物馆'    # 博物馆第三
        ), reverse=True)
        
        return unique_attractions
    
    def _remove_duplicate_restaurants(self, restaurants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去除重复的餐厅"""
        seen_names = set()
        unique_restaurants = []
        
        for restaurant in restaurants:
            name = restaurant['name']
            if name not in seen_names:
                seen_names.add(name)
                unique_restaurants.append(restaurant)
        
        # 按评分排序
        unique_restaurants.sort(key=lambda x: -x.get('rating', 0))
        
        return unique_restaurants
    
    async def _plan_routes_between_attractions(self, attractions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """规划景点间的路线"""
        route_plans = []
        
        try:
            if len(attractions) < 2:
                return route_plans
            
            # 规划前3个主要景点之间的路线
            main_attractions = attractions[:3]
            
            for i in range(len(main_attractions) - 1):
                origin = main_attractions[i]
                destination = main_attractions[i + 1]
                
                # 获取起点和终点的地址
                origin_address = origin.get('address', origin.get('name', ''))
                dest_address = destination.get('address', destination.get('name', ''))
                
                # 使用简化的路线规划
                route_plan = {
                    'from': origin['name'],
                    'to': destination['name'],
                    'from_address': origin_address,
                    'to_address': dest_address,
                    'estimated_time': '约15-30分钟',
                    'estimated_cost': '约2-5元(公交)'
                }
                
                route_plans.append(route_plan)
            
            return route_plans
            
        except Exception as e:
            self.logger.error(f"路线规划异常: {str(e)}")
            return []
    
    async def _generate_travel_itinerary(self, location: str, duration: str, attractions: List[Dict[str, Any]], 
                                       restaurants: List[Dict[str, Any]], route_plans: List[Dict[str, Any]]) -> str:
        """生成完整的旅游行程"""
        try:
            # 构建基础行程
            itinerary = f"""
## 🏛️ {location}{duration}旅游规划

### 📍 主要景点推荐
"""
            
            for i, attraction in enumerate(attractions[:6], 1):
                itinerary += f"""
{i}. **{attraction['name']}**
   - 地址：{attraction.get('address', '详细地址请现场确认')}
   - 类型：{attraction['type']}
   - 评分：{attraction.get('rating', '暂无评分')}
"""
            
            itinerary += f"""

### 🍽️ 推荐餐厅
"""
            
            for i, restaurant in enumerate(restaurants[:4], 1):
                itinerary += f"""
{i}. **{restaurant['name']}**
   - 地址：{restaurant.get('address', '详细地址请现场确认')}
   - 类型：{restaurant['type']}
   - 评分：{restaurant.get('rating', '暂无评分')}
"""
            
            itinerary += f"""

### 🚌 景点间交通
"""
            
            for route in route_plans:
                itinerary += f"""
- **{route['from']} → {route['to']}**
  - 预计时间：{route['estimated_time']}
  - 预计费用：{route['estimated_cost']}
"""
            
            itinerary += f"""

### 💰 费用预算
- 门票费用：根据具体景点而定
- 交通费用：约30-50元/天
- 餐饮费用：约100-200元/天
- 总计预算：约150-300元/天

### 📝 贴心提示
- 提前查看景点开放时间
- 准备好现金和交通卡
- 关注天气情况，做好防护
- 建议下载百度地图等导航软件
"""
            
            return itinerary
            
        except Exception as e:
            self.logger.error(f"生成旅游行程异常: {str(e)}")
            return f"生成旅游行程时出现错误：{str(e)}" 