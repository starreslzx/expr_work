import json
from typing import Dict, List, Any
import os


class TopicGraph:
    """话题图结构 - 基于related_topics建立连接"""

    def __init__(self, json_file: str):
        self.chat_groups: List[Dict[str, Any]] = []  # 聊天群组存储
        self.graph: Dict[str, List[str]] = {}  # 图结构存储
        self.json_file = json_file

        # 从JSON文件加载数据
        self.load_from_json(json_file)

    def load_from_json(self, json_file: str):
        """从JSON文件加载数据"""
        try:
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.chat_groups = data.get('chat_groups', [])
                print(f"从 {json_file} 加载成功: {len(self.chat_groups)}个群组, {self._count_topics()}个话题")
            else:
                print(f"文件 {json_file} 不存在，创建新文件")
                self.chat_groups = []

            # 构建图结构
            self._build_graph_from_data()

        except json.JSONDecodeError as e:
            print(f"JSON文件格式错误: {e}")
            self.chat_groups = []
            self._build_graph_from_data()

    def _build_graph_from_data(self):
        """从聊天数据构建图结构 - 基于related_topics建立连接"""
        self.graph = {}

        # 首先初始化所有话题节点
        for group in self.chat_groups:
            for topic in group.get('topics', []):
                topic_id = topic['topic_id']
                self.graph[topic_id] = []

        # 基于related_topics建立连接
        connection_count = 0
        for group in self.chat_groups:
            for topic in group.get('topics', []):
                topic_id = topic['topic_id']
                topic_name = topic['topic_name']

                # 为每个related_topics建立连接
                for related_topic_name in topic.get('related_topics', []):
                    related_topic_id = self._find_topic_id_by_name(related_topic_name)
                    if related_topic_id and related_topic_id != topic_id:
                        # 建立连接
                        if related_topic_id not in self.graph[topic_id]:
                            self.graph[topic_id].append(related_topic_id)
                            connection_count += 1

        print(f"图结构构建完成: {len(self.graph)}个节点, {connection_count}个连接")

    def _find_topic_id_by_name(self, topic_name: str) -> str:
        """根据话题名称查找话题ID"""
        for group in self.chat_groups:
            for topic in group.get('topics', []):
                if topic['topic_name'] == topic_name:
                    return topic['topic_id']
        return ""

    def _count_topics(self):
        """计算话题总数"""
        count = 0
        for group in self.chat_groups:
            count += len(group.get('topics', []))
        return count

    def save_to_json(self):
        """保存到JSON文件"""
        data = {
            'chat_groups': self.chat_groups
        }

        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"数据已保存到 {self.json_file}")

    def add_topic_from_json_file(self):
        """从JSON文件添加话题"""
        print("\n=== 从JSON文件添加话题 ===")

        # 获取JSON文件路径
        json_file_path = input("请输入包含话题数据的JSON文件路径: ").strip()
        if not json_file_path:
            print("文件路径不能为空")
            return

        try:
            # 读取JSON文件
            with open(json_file_path, 'r', encoding='utf-8') as f:
                topic_data = json.load(f)

            # 处理单个话题
            if "topic_id" in topic_data and "topic_name" in topic_data:
                # 这是单个话题的格式
                group_id = topic_data.get("group_id", "default_group")
                self._add_single_topic_from_data(group_id, topic_data)

            # 处理包含多个话题的数组
            elif isinstance(topic_data, list):
                for topic_item in topic_data:
                    if "topic_id" in topic_item and "topic_name" in topic_item:
                        group_id = topic_item.get("group_id", "default_group")
                        self._add_single_topic_from_data(group_id, topic_item)

            # 处理包含topics数组的对象
            elif "topics" in topic_data:
                group_id = topic_data.get("group_id", "default_group")
                topics_data = topic_data["topics"]
                for topic_item in topics_data:
                    self._add_single_topic_from_data(group_id, topic_item)

            else:
                print("JSON格式错误：无法识别的话题数据格式")
                return False

            # 重新构建图结构
            self._build_graph_from_data()

            # 保存到文件
            self.save_to_json()

            return True

        except FileNotFoundError:
            print(f"文件 {json_file_path} 不存在")
            return False
        except json.JSONDecodeError as e:
            print(f"JSON文件格式错误: {e}")
            return False
        except Exception as e:
            print(f"添加话题时出错: {e}")
            return False

    def _add_single_topic_from_data(self, group_id: str, topic_data: Dict):
        """添加单个话题"""
        # 查找或创建群组
        group = None
        for g in self.chat_groups:
            if g['group_id'] == group_id:
                group = g
                break

        if not group:
            # 创建新群组
            group = {
                "group_id": group_id,
                "group_name": f"群组{group_id}",
                "description": "",
                "topics": []
            }
            self.chat_groups.append(group)

        # 使用提供的topic_id或生成新的
        if "topic_id" in topic_data and topic_data["topic_id"]:
            topic_id = topic_data["topic_id"]
            # 检查topic_id是否已存在
            for existing_topic in group['topics']:
                if existing_topic['topic_id'] == topic_id:
                    print(f"话题ID {topic_id} 已存在，将使用新ID")
                    topic_id = f"topic_{group_id}_{len(group['topics']) + 1:02d}"
                    break
        else:
            # 生成新ID
            topic_id = f"topic_{group_id}_{len(group['topics']) + 1:02d}"

        # 创建新话题
        new_topic = {
            "topic_id": topic_id,
            "topic_name": topic_data['topic_name'],
            "priority": topic_data.get('priority', '中'),
            "summaries": topic_data.get('summaries', []),
            "related_records": topic_data.get('related_records', []),
            "related_topics": topic_data.get('related_topics', [])
        }

        group['topics'].append(new_topic)

        # 初始化图结构
        self.graph[topic_id] = []

        print(f"添加话题: {topic_data['topic_name']} (ID: {topic_id})")

        # 建立与相关话题的连接
        for related_topic_name in new_topic.get('related_topics', []):
            related_topic_id = self._find_topic_id_by_name(related_topic_name)
            if related_topic_id and related_topic_id != topic_id:
                if related_topic_id not in self.graph[topic_id]:
                    self.graph[topic_id].append(related_topic_id)
                    print(f"  连接: {topic_data['topic_name']} -> {related_topic_name}")

    def get_topic_name_by_id(self, topic_id: str) -> str:
        """根据话题ID获取话题名称"""
        for group in self.chat_groups:
            for topic in group.get('topics', []):
                if topic['topic_id'] == topic_id:
                    return topic['topic_name']
        return ""

    def get_topic_details(self, topic_id: str) -> Dict:
        """获取话题详细信息"""
        for group in self.chat_groups:
            for topic in group.get('topics', []):
                if topic['topic_id'] == topic_id:
                    return topic
        return {}

    def show_topic_details(self, topic_id: str):
        """显示话题详情"""
        topic = self.get_topic_details(topic_id)
        if not topic:
            print(f"话题 {topic_id} 不存在")
            return

        print(f"\n=== 话题详情: {topic['topic_name']} ===")
        print(f"话题ID: {topic_id}")
        print(f"优先级: {topic['priority']}")

        print("\n话题总结:")
        for i, summary in enumerate(topic.get('summaries', []), 1):
            print(f"{i}. {summary}")

        print("\n相关聊天记录:")
        for record in topic.get('related_records', []):
            print(f"- {record}")

        # 显示相关话题
        related_topics = topic.get('related_topics', [])
        if related_topics:
            print(f"\n相关话题 ({len(related_topics)}个):")
            for related_topic_name in related_topics:
                related_topic_id = self._find_topic_id_by_name(related_topic_name)
                if related_topic_id:
                    if related_topic_id in self.graph.get(topic_id, []):
                        print(f"  ✓ {related_topic_name}")
                    else:
                        print(f"  ✗ {related_topic_name} (未连接)")
                else:
                    print(f"  ? {related_topic_name} (话题不存在)")

        # 显示连接信息
        connections = self.graph.get(topic_id, [])
        if connections:
            print(f"\n连接到的其他话题 ({len(connections)}个):")
            for connected_id in connections:
                connected_name = self.get_topic_name_by_id(connected_id)
                if connected_name:
                    print(f"  → {connected_name}")

    def list_all_topics(self):
        """列出所有话题"""
        print("\n=== 所有话题 ===")
        topic_count = 0
        for group in self.chat_groups:
            print(f"\n群组: {group['group_name']} ({group['group_id']})")
            for topic in group.get('topics', []):
                topic_count += 1
                connections = len(self.graph.get(topic['topic_id'], []))
                print(
                    f"  {topic['topic_id']}: {topic['topic_name']} (优先级: {topic['priority']}, 连接数: {connections})")

        print(f"\n总计: {topic_count}个话题")

    def search_topics(self, keyword: str):
        """搜索话题"""
        print(f"\n=== 搜索话题: '{keyword}' ===")
        found = False
        for group in self.chat_groups:
            for topic in group.get('topics', []):
                if (keyword.lower() in topic['topic_name'].lower() or
                        any(keyword.lower() in summary.lower() for summary in topic.get('summaries', []))):

                    print(f"\n找到话题: {topic['topic_name']}")
                    print(f"  群组: {group['group_name']}")
                    print(f"  ID: {topic['topic_id']}")
                    print(f"  优先级: {topic['priority']}")

                    # 显示连接
                    connections = self.graph.get(topic['topic_id'], [])
                    if connections:
                        connected_names = [self.get_topic_name_by_id(conn_id) for conn_id in connections]
                        print(f"  连接: {', '.join([name for name in connected_names if name])}")

                    found = True

        if not found:
            print("未找到相关话题")

    def show_graph_structure(self):
        """显示图结构"""
        print("\n=== 话题图结构 ===")

        total_connections = 0
        for topic_id, connections in self.graph.items():
            if connections:
                topic_name = self.get_topic_name_by_id(topic_id)
                connected_names = [self.get_topic_name_by_id(conn_id) for conn_id in connections]
                print(f"{topic_name} -> {', '.join([name for name in connected_names if name])}")
                total_connections += len(connections)

        print(f"\n图结构统计:")
        print(f"  节点数: {len(self.graph)}")
        print(f"  连接数: {total_connections}")
        print(f"  群组数: {len(self.chat_groups)}")
        print(f"  话题总数: {self._count_topics()}")


def main():
    """主函数"""
    print("=== 话题图管理系统 ===")

    # 获取JSON文件路径
    json_file = input("请输入JSON文件路径 (直接回车使用默认路径): ").strip()
    if not json_file:
        json_file = "chat_topics.json"
        print(f"使用默认文件: {json_file}")

    # 创建话题图
    graph = TopicGraph(json_file)

    while True:
        print("\n" + "=" * 50)
        print("1. 显示所有话题")
        print("2. 显示图结构")
        print("3. 从JSON文件添加话题")
        print("4. 查看话题详情")
        print("5. 搜索话题")
        print("6. 保存数据")
        print("7. 退出")

        choice = input("\n请选择操作 (1-7): ").strip()

        if choice == "1":
            graph.list_all_topics()

        elif choice == "2":
            graph.show_graph_structure()

        elif choice == "3":
            graph.add_topic_from_json_file()

        elif choice == "4":
            topic_id = input("输入话题ID: ").strip()
            graph.show_topic_details(topic_id)

        elif choice == "5":
            keyword = input("输入搜索关键词: ").strip()
            graph.search_topics(keyword)

        elif choice == "6":
            graph.save_to_json()

        elif choice == "7":
            # 退出前保存
            save = input("退出前是否保存数据? (y/n, 默认y): ").strip().lower()
            if save != "n":
                graph.save_to_json()
            print("再见!")
            break

        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    main()