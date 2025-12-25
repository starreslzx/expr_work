import json
import re
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI


class Searcher:
    def __init__(self, data_file: str = "data.json", token_file: str = "api_token.txt"):
        # 初始化搜索器，加载数据和API客户端
        self.data_file = self._resolve_file_path(data_file)
        self.token_file = self._resolve_file_path(token_file)
        self.data = self._load_data()
        self.client = self._init_openai_client()

    def _resolve_file_path(self, file_path: str) -> str:
        # 解析文件路径，尝试多个可能位置
        if os.path.isabs(file_path):
            return file_path

        possible_paths = [
            file_path,
            os.path.join(os.path.dirname(__file__), file_path),
            os.path.join(os.path.dirname(__file__), "..", file_path),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return os.path.abspath(path)

        return os.path.abspath(file_path)

    def _load_data(self) -> Dict[str, Any]:
        # 加载JSON数据文件，支持注释
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                content = f.read()

            content = re.sub(r'^\s*#.*$', '', content, flags=re.MULTILINE)

            return json.loads(content)
        except FileNotFoundError:
            raise Exception(f"数据文件 {self.data_file} 未找到。请检查文件路径。")
        except json.JSONDecodeError:
            raise Exception(f"数据文件 {self.data_file} 格式错误")

    def _init_openai_client(self) -> OpenAI:
        # 从token文件初始化OpenAI客户端
        try:
            with open(self.token_file, 'r', encoding='utf-8') as f:
                api_key = f.read().strip()

            return OpenAI(
                api_key=api_key,
                base_url="https://api-inference.modelscope.cn/v1/"
            )
        except FileNotFoundError:
            raise Exception(f"API token文件 {self.token_file} 未找到。请检查文件路径。")

    def keyword_search(self, query: str, fields: List[str] = None,
                       group_name: str = None, topic_name: str = None) -> List[Dict[str, Any]]:
        # 关键词搜索，在指定字段中查找匹配项
        if fields is None:
            fields = ['group_name', 'topic_name', 'summaries', 'related_topics']

        results = []
        query_lower = query.lower()
        group_name_lower = group_name.lower() if group_name else None
        topic_name_lower = topic_name.lower() if topic_name else None

        for group in self.data.get('chat_groups', []):
            if group_name_lower and group_name_lower not in group.get('group_name', '').lower():
                continue

            for topic in group.get('topics', []):
                if topic_name_lower and topic_name_lower not in topic.get('topic_name', '').lower():
                    continue

                score = 0
                match_details = []

                if 'group_name' in fields:
                    group_name_val = group.get('group_name', '').lower()
                    if query_lower in group_name_val:
                        score += 3
                        match_details.append(f"群组名称匹配: {group['group_name']}")

                if 'topic_name' in fields:
                    topic_name_val = topic.get('topic_name', '').lower()
                    if query_lower in topic_name_val:
                        score += 3
                        match_details.append(f"主题名称匹配: {topic['topic_name']}")

                if 'summaries' in fields:
                    for i, summary in enumerate(topic.get('summaries', [])):
                        if query_lower in summary.lower():
                            score += 2
                            match_details.append(f"摘要匹配: {summary}")

                if 'related_topics' in fields:
                    for related_topic in topic.get('related_topics', []):
                        if query_lower in related_topic.lower():
                            score += 2
                            match_details.append(f"相关主题匹配: {related_topic}")

                if score > 0:
                    result = {
                        'topic_id': topic['topic_id'],
                        'topic_name': topic['topic_name'],
                        'priority': topic['priority'],
                        'summaries': topic['summaries'],
                        'related_topics': topic.get('related_topics', []),
                        'group_info': {
                            'group_id': group['group_id'],
                            'group_name': group['group_name'],
                            'description': group['description']
                        },
                        'search_score': score,
                        'match_details': match_details,
                        'search_type': 'keyword'
                    }
                    results.append(result)

        results.sort(key=lambda x: x['search_score'], reverse=True)
        return results

    def ai_semantic_search(self, query: str, max_results: int = 10,
                           group_name: str = None, topic_name: str = None,
                           use_batch_mode: bool = False, batch_size: int = 20,
                           exclude_topic_ids: List[str] = None) -> List[Dict[str, Any]]:
        # AI语义搜索，可选择分批处理
        if use_batch_mode:
            return self._ai_semantic_search_batch(query, max_results, group_name, topic_name, batch_size,
                                                  exclude_topic_ids)
        else:
            return self._ai_semantic_search_single(query, max_results, group_name, topic_name, exclude_topic_ids)

    def _ai_semantic_search_single(self, query: str, max_results: int = 10,
                                   group_name: str = None, topic_name: str = None,
                                   exclude_topic_ids: List[str] = None) -> List[Dict[str, Any]]:
        # 单批AI语义搜索
        context = self._build_search_context(group_name, topic_name, exclude_topic_ids)

        if not context:
            print("没有找到符合条件的数据用于AI搜索")
            return []

        prompt = f"""
        你是一个微信聊天总结的智能搜索助手。请根据用户查询，从提供的聊天主题数据中找出语义上相关的内容。

        用户查询: "{query}"

        可用的聊天主题数据:
        {context}

        请分析用户查询的意图，并推荐相关的聊天主题。考虑以下因素:
        1. 主题相关性 (即使没有完全匹配的关键词)
        2. 技术概念的关联性
        3. 业务场景的相似性
        4. 用户可能的深层需求

        重要限制：每个群聊最多只能推荐3个话题！

        请以JSON格式返回结果，包含以下字段:
        - recommended_topics: 推荐的主题ID列表 (最多{max_results}个)
        - reasoning: 推荐理由的简要说明
        - confidence: 整体推荐置信度 (0-1)

        只返回JSON格式的结果，不要其他内容。
        """

        try:
            response = self.client.chat.completions.create(
                model="Qwen/Qwen2.5-Coder-32B-Instruct",
                messages=[
                    {
                        'role': 'system',
                        'content': '你是一个专业的搜索助手，擅长理解技术文档和聊天记录的语义关联。请确保每个群聊最多推荐3个话题。'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                temperature=0.3
            )

            ai_response = response.choices[0].message.content
            results = self._parse_ai_response(ai_response, max_results, group_name, topic_name)

            return self._limit_results_per_group(results, max_results)

        except Exception as e:
            print(f"AI搜索出错: {e}")
            return []

    def _ai_semantic_search_batch(self, query: str, max_results: int = 10,
                                  group_name: str = None, topic_name: str = None,
                                  batch_size: int = 20, exclude_topic_ids: List[str] = None) -> List[Dict[str, Any]]:
        # 分批AI语义搜索，处理大量数据
        all_topics = self._get_all_topics(group_name, topic_name, exclude_topic_ids)

        if not all_topics:
            print("没有找到符合条件的数据用于AI搜索")
            return []

        batches = [all_topics[i:i + batch_size] for i in range(0, len(all_topics), batch_size)]
        all_results = []

        print(f"数据量较大，将分 {len(batches)} 批进行AI搜索...")

        for i, batch in enumerate(batches):
            print(f"正在处理第 {i + 1}/{len(batches)} 批数据...")

            context = self._build_batch_context(batch)

            prompt = f"""
            你是一个微信聊天总结的智能搜索助手。请根据用户查询，从提供的聊天主题数据中找出语义上相关的内容。

            用户查询: "{query}"

            可用的聊天主题数据 (第 {i + 1} 批，共 {len(batches)} 批):
            {context}

            请分析用户查询的意图，并推荐相关的聊天主题。考虑以下因素:
            1. 主题相关性 (即使没有完全匹配的关键词)
            2. 技术概念的关联性
            3. 业务场景的相似性
            4. 用户可能的深层需求
            5. 不必执着于第4条 ，如果你认为是输入错误或确实无关联，可以返回空
            重要限制：每个群聊最多只能推荐3个话题！

            请以JSON格式返回结果，包含以下字段:
            - recommended_topics: 推荐的主题ID列表
            - reasoning: 推荐理由的简要说明
            - confidence: 整体推荐置信度 (0-1)

            只返回JSON格式的结果，不要其他内容。
            """

            try:
                response = self.client.chat.completions.create(
                    model="Qwen/Qwen2.5-Coder-32B-Instruct",
                    messages=[
                        {
                            'role': 'system',
                            'content': '你是一个专业的搜索助手，擅长理解技术文档和聊天记录的语义关联。请确保每个群聊最多推荐3个话题。'
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    temperature=0.3
                )

                ai_response = response.choices[0].message.content
                batch_results = self._parse_ai_response(ai_response, max_results, group_name, topic_name)
                all_results.extend(batch_results)

            except Exception as e:
                print(f"第 {i + 1} 批AI搜索出错: {e}")
                continue

        all_results.sort(key=lambda x: x['confidence'], reverse=True)
        return self._limit_results_per_group(all_results, max_results)

    def _limit_results_per_group(self, results: List[Dict[str, Any]], max_results: int) -> List[Dict[str, Any]]:
        # 限制每个群聊最多返回3个结果
        grouped_results = {}

        for result in results:
            group_id = result['topic_info']['group_info']['group_id']
            if group_id not in grouped_results:
                grouped_results[group_id] = []
            grouped_results[group_id].append(result)

        limited_results = []
        for group_id, group_results in grouped_results.items():
            group_results_sorted = sorted(group_results, key=lambda x: x['confidence'], reverse=True)
            limited_results.extend(group_results_sorted[:3])

        limited_results.sort(key=lambda x: x['confidence'], reverse=True)
        return limited_results[:max_results]

    def _get_all_topics(self, group_name: str = None, topic_name: str = None, exclude_topic_ids: List[str] = None) -> \
    List[Dict[str, Any]]:
        # 获取所有话题，支持过滤条件
        all_topics = []
        group_name_lower = group_name.lower() if group_name else None
        topic_name_lower = topic_name.lower() if topic_name else None
        exclude_set = set(exclude_topic_ids) if exclude_topic_ids else set()

        for group in self.data.get('chat_groups', []):
            if group_name_lower and group_name_lower not in group.get('group_name', '').lower():
                continue

            for topic in group.get('topics', []):
                if topic_name_lower and topic_name_lower not in topic.get('topic_name', '').lower():
                    continue

                if topic['topic_id'] in exclude_set:
                    continue

                all_topics.append({
                    'topic': topic,
                    'group': group
                })

        return all_topics

    def _build_batch_context(self, batch: List[Dict[str, Any]]) -> str:
        # 构建批量处理的上下文信息
        context_parts = []

        for item in batch:
            topic = item['topic']
            group = item['group']

            topic_info = [
                f"主题: {topic['topic_name']} (ID: {topic['topic_id']})",
                f"群组: {group['group_name']}",
                f"优先级: {topic['priority']}",
                f"摘要: {'; '.join(topic['summaries'])}"
            ]

            if topic.get('related_topics'):
                topic_info.append(f"相关主题: {', '.join(topic['related_topics'])}")

            context_parts.append("\n".join(topic_info) + "\n---")

        return "\n".join(context_parts)

    def _build_search_context(self, group_name: str = None, topic_name: str = None,
                              exclude_topic_ids: List[str] = None) -> str:
        # 构建AI搜索的上下文信息
        context_parts = []
        group_name_lower = group_name.lower() if group_name else None
        topic_name_lower = topic_name.lower() if topic_name else None
        exclude_set = set(exclude_topic_ids) if exclude_topic_ids else set()

        for group in self.data.get('chat_groups', []):
            if group_name_lower and group_name_lower not in group.get('group_name', '').lower():
                continue

            for topic in group.get('topics', []):
                if topic_name_lower and topic_name_lower not in topic.get('topic_name', '').lower():
                    continue

                if topic['topic_id'] in exclude_set:
                    continue

                topic_info = [
                    f"主题: {topic['topic_name']} (ID: {topic['topic_id']})",
                    f"群组: {group['group_name']}",
                    f"优先级: {topic['priority']}",
                    f"摘要: {'; '.join(topic['summaries'])}"
                ]

                if topic.get('related_topics'):
                    topic_info.append(f"相关主题: {', '.join(topic['related_topics'])}")

                context_parts.append("\n".join(topic_info) + "\n---")

        return "\n".join(context_parts)

    def _parse_ai_response(self, ai_response: str, max_results: int,
                           group_name: str = None, topic_name: str = None) -> List[Dict[str, Any]]:
        # 解析AI返回的JSON响应
        try:
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())

                recommended_topics = result_data.get('recommended_topics', [])[:max_results * 2]
                results = []

                for topic_id in recommended_topics:
                    topic_info = self._find_topic_by_id(topic_id, group_name, topic_name)
                    if topic_info:
                        results.append({
                            'topic_info': topic_info,
                            'reasoning': result_data.get('reasoning', ''),
                            'confidence': result_data.get('confidence', 0.5),
                            'search_type': 'ai_semantic'
                        })

                return results
            else:
                print("无法解析AI返回的JSON格式")
                print(f"AI返回内容: {ai_response}")
                return []

        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"AI返回内容: {ai_response}")
            return []

    def _find_topic_by_id(self, topic_id: str, group_name: str = None, topic_name: str = None) -> Optional[
        Dict[str, Any]]:
        # 根据话题ID查找话题信息
        group_name_lower = group_name.lower() if group_name else None
        topic_name_lower = topic_name.lower() if topic_name else None

        for group in self.data.get('chat_groups', []):
            if group_name_lower and group_name_lower not in group.get('group_name', '').lower():
                continue

            for topic in group.get('topics', []):
                if topic_name_lower and topic_name_lower not in topic.get('topic_name', '').lower():
                    continue

                if topic['topic_id'] == topic_id:
                    result = {
                        'topic_id': topic['topic_id'],
                        'topic_name': topic['topic_name'],
                        'priority': topic['priority'],
                        'summaries': topic['summaries'],
                        'related_topics': topic.get('related_topics', []),
                        'group_info': {
                            'group_id': group['group_id'],
                            'group_name': group['group_name'],
                            'description': group['description']
                        }
                    }
                    return result
        return None

    def search(self, query: str, use_ai: bool = True,
               ai_max_results: int = 10, group_name: str = None, topic_name: str = None,
               use_batch_mode: bool = False, batch_size: int = 20) -> Dict[str, Any]:
        # 综合搜索接口，结合关键词和AI搜索
        keyword_results = self.keyword_search(
            query,
            group_name=group_name,
            topic_name=topic_name
        )

        ai_results = []
        if use_ai and query.strip():
            exclude_topic_ids = [result['topic_id'] for result in keyword_results]
            ai_results = self.ai_semantic_search(
                query,
                max_results=ai_max_results,
                group_name=group_name,
                topic_name=topic_name,
                use_batch_mode=use_batch_mode,
                batch_size=batch_size,
                exclude_topic_ids=exclude_topic_ids
            )

        return {
            'query': query,
            'keyword_results': keyword_results,
            'ai_recommendations': ai_results,
            'search_filters': {
                'group_name': group_name,
                'topic_name': topic_name
            },
            'stats': {
                'keyword_matches': len(keyword_results),
                'ai_recommendations': len(ai_results)
            }
        }

    def display_results(self, search_results: Dict[str, Any]):
        # 在控制台格式化显示搜索结果
        print(f"\n搜索查询: {search_results['query']} ")

        filters = search_results['search_filters']
        if filters['group_name'] or filters['topic_name']:
            print("搜索范围:")
            if filters['group_name']:
                print(f"  - 群聊: {filters['group_name']}")
            if filters['topic_name']:
                print(f"  - 话题: {filters['topic_name']}")
            print()

        print(f"关键词匹配: {search_results['stats']['keyword_matches']} 个")
        print(f"AI推荐: {search_results['stats']['ai_recommendations']} 个\n")

        if search_results['keyword_results']:
            print("关键词匹配结果:")
            for i, result in enumerate(search_results['keyword_results'], 1):
                print(f"{i}. [{result['group_info']['group_name']}] {result['topic_name']} "
                      f"(优先级: {result['priority']}, 匹配度: {result['search_score']})")
                if result.get('summaries'):
                    print(f"   摘要: {result['summaries'][0]}")
                if result.get('related_topics'):
                    print(f"   相关主题: {', '.join(result['related_topics'])}")
                for detail in result['match_details'][:2]:
                    print(f"   - {detail}")
                print()

        if search_results['ai_recommendations']:
            print("AI智能推荐 (每个群聊最多3个):")
            for i, result in enumerate(search_results['ai_recommendations'], 1):
                topic = result['topic_info']
                print(f"{i}. [{topic['group_info']['group_name']}] {topic['topic_name']} "
                      f"(置信度: {result['confidence']:.2f})")
                if topic.get('summaries'):
                    print(f"   摘要: {topic['summaries'][0]}")
                if topic.get('related_topics'):
                    print(f"   相关主题: {', '.join(topic['related_topics'])}")
                print(f"   理由: {result['reasoning']}")
                print()

    def get_available_groups(self) -> List[str]:
        # 获取所有可用的群聊名称
        groups = []
        for group in self.data.get('chat_groups', []):
            groups.append(group['group_name'])
        return sorted(groups)

    def get_available_topics(self, group_name: str = None) -> List[str]:
        # 获取所有可用的话题名称，支持按群聊过滤
        topics = []
        group_name_lower = group_name.lower() if group_name else None

        for group in self.data.get('chat_groups', []):
            if group_name_lower and group_name_lower not in group.get('group_name', '').lower():
                continue

            for topic in group.get('topics', []):
                topics.append(topic['topic_name'])
        return sorted(topics)
