import httpx
import requests
import traceback
import re
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
                    }
                },
                "examples": [
                    "制定北京一日游行程",
                    "规划杭州2天旅游路线",
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
            
            return {
                "status": "success",
                "route_data": result,
                "origin": origin,
                "destination": destination,
                "mode": mode
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
            
            if not location:
                return {
                    "status": "error",
                    "message": "缺少必需参数: location"
                }
            
            # 使用增强的旅游规划功能
            travel_result = await self._enhanced_travel_planning(location, duration, interests)
            
            return {
                "status": "success",
                "travel_plan": travel_result,
                "location": location,
                "duration": duration,
                "interests": interests
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
                
                for transport in transport_modes:
                    route_result = await self._get_route_for_mode(
                        origin_coord, dest_coord, transport["mode"], transport["name"]
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
    
    async def _get_route_for_mode(self, origin_coord: str, dest_coord: str, mode: str, mode_name: str) -> Dict[str, Any]:
        """获取特定交通方式的路线"""
        try:
            endpoint = f"{self.base_url}/baidu-map/map_directions"
            request_body = {
                "origin": origin_coord,
                "destination": dest_coord,
                "mode": mode
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=request_body)
                
                if response.status_code == 200:
                    result = response.json()
                    route_info = self._parse_route_result(result, mode_name)
                    if route_info:
                        return {
                            "transport_mode": mode_name,
                            "mode": mode,
                            "route_info": route_info,
                            "raw_result": result
                        }
                else:
                    self.logger.warning(f"{mode_name}路线获取失败: {response.text}")
                    
        except Exception as e:
            self.logger.warning(f"{mode_name}路线获取异常: {e}")
        
        return None
    
    def _parse_route_result(self, result: Dict[str, Any], transport_name: str) -> str:
        """解析路线结果"""
        try:
            if not result or 'result' not in result:
                return f"抱歉，无法获取{transport_name}路线信息"
            
            routes = result['result']['routes']
            if not routes:
                return f"未找到{transport_name}路线"
            
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
                
                for i, step in enumerate(steps):
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
            
            # 费用估算
            if transport_name == "公交":
                description += f"\n• 总费用：约2-4元"
            elif transport_name == "地铁":
                description += f"\n• 总费用：约3-6元"
            elif transport_name == "驾车":
                fuel_cost = distance_km * 0.8
                description += f"\n• 总费用：约{fuel_cost:.1f}元(油费)"
            
            return description
            
        except Exception as e:
            self.logger.error(f"解析{transport_name}路线时出错: {str(e)}")
            return f"解析{transport_name}路线时出现错误"
    
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