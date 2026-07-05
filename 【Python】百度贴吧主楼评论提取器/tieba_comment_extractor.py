#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度贴吧主楼评论提取器

功能说明：
1. 解析HAR文件，提取百度贴吧评论数据
2. 提取主评论并保存为JSON格式
3. 支持筛选特定作者的评论
4. 支持提取纯文本内容
5. 支持过滤表情符号

使用方式：
python tieba_comment_extractor.py <har_file> [options]
"""

import os
import sys
import json
import base64
import re
import tempfile
import shutil
import argparse


class TiebaCommentExtractor:
    """百度贴吧评论提取器主类"""
    
    def __init__(self, har_file, temp_dir=None):
        """
        初始化提取器
        
        Args:
            har_file: HAR文件路径
            temp_dir: 临时文件夹路径，默认为系统临时目录
        """
        self.har_file = har_file
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="tieba_")
        self.main_comments_file = "main_comments.json"
        self.filtered_comments_file = "filtered_comments.json"
        self.extracted_texts_file = "extracted_texts.txt"
    
    def __del__(self):
        """清理临时文件"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def parse_har_file(self):
        """
        解析HAR文件，提取百度贴吧评论相关的POST请求
        
        Returns:
            list: 解析成功的JSON文件列表
        """
        print(f"[1/5] 正在解析HAR文件: {self.har_file}")
        
        try:
            with open(self.har_file, 'r', encoding='utf-8') as f:
                har_data = json.load(f)
        except FileNotFoundError:
            print(f"错误: 找不到文件 {self.har_file}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"错误: {self.har_file} 不是有效的JSON文件")
            sys.exit(1)
        
        entries = har_data.get('log', {}).get('entries', [])
        
        # 筛选包含'page_pc'的POST请求
        filtered_entries = []
        for entry in entries:
            request = entry.get('request', {})
            method = request.get('method', '').upper()
            url = request.get('url', '')
            
            if method == 'POST' and 'page_pc' in url:
                filtered_entries.append(entry)
        
        if not filtered_entries:
            print("错误: 未找到符合条件的POST请求")
            sys.exit(1)
        
        print(f"找到 {len(filtered_entries)} 个符合条件的POST请求")
        
        # 按时间排序
        filtered_entries.sort(key=lambda x: x.get('startedDateTime', ''))
        
        # 解析响应体并保存为JSON文件
        parsed_files = []
        for i, entry in enumerate(filtered_entries, 1):
            response = entry.get('response', {})
            content = response.get('content', {})
            text = content.get('text', '')
            
            print(f'处理第{i}个请求: {entry.get("request", {}).get("url", "")}')
            print(f'响应状态: {response.get("status", "N/A")}')
            print(f'响应体长度: {len(text) if text else 0}')
            
            if text:
                try:
                    # 尝试直接解析JSON
                    response_body = json.loads(text)
                    output_file = os.path.join(self.temp_dir, f'page_pc{i}.json')
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(response_body, f, ensure_ascii=False, indent=2)
                    
                    parsed_files.append(output_file)
                    print(f'导出成功: {os.path.basename(output_file)}')
                except json.JSONDecodeError:
                    # 尝试Base64解码后再解析
                    try:
                        decoded_text = base64.b64decode(text).decode('utf-8')
                        response_body = json.loads(decoded_text)
                        output_file = os.path.join(self.temp_dir, f'page_pc{i}.json')
                        
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(response_body, f, ensure_ascii=False, indent=2)
                        
                        parsed_files.append(output_file)
                        print(f'Base64解码后导出成功: {os.path.basename(output_file)}')
                    except Exception as e:
                        print(f'警告: 第{i}个响应体无法解析: {str(e)}')
            else:
                print(f'警告: 第{i}个响应体为空')
            
            print('-' * 50)
        
        print(f'完成处理，共导出 {len(parsed_files)} 个文件到临时目录')
        return parsed_files
    
    def extract_main_comments(self, json_files):
        """
        从JSON文件中提取主评论
        
        Args:
            json_files: JSON文件列表
            
        Returns:
            list: 主评论列表
        """
        print(f"\n[2/5] 正在提取主评论...")
        
        all_comments = []
        
        for file_path in json_files:
            file_name = os.path.basename(file_path)
            print(f"处理 {file_name}...")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if 'post_list' in data:
                    for post in data['post_list']:
                        # 提取主要字段
                        comment = {
                            'id': post.get('id'),
                            'floor': post.get('floor'),
                            'time': post.get('time'),
                            'author_id': post.get('author_id'),
                            'content': post.get('content'),
                            'sub_post_number': post.get('sub_post_number'),
                            'agree': post.get('agree'),
                            'title': post.get('title')
                        }
                        all_comments.append(comment)
            except json.JSONDecodeError as e:
                print(f"错误解析 {file_name}: {e}")
        
        if not all_comments:
            print("错误: 未提取到任何评论")
            sys.exit(1)
        
        # 按楼层排序
        all_comments.sort(key=lambda x: x.get('floor', 0))
        
        # 保存到文件
        with open(self.main_comments_file, 'w', encoding='utf-8') as f:
            json.dump(all_comments, f, ensure_ascii=False, indent=2)
        
        print(f"提取 {len(all_comments)} 条主评论到 {self.main_comments_file}")
        return all_comments
    
    def filter_by_author(self, author_id):
        """
        筛选特定作者的评论
        
        Args:
            author_id: 作者ID
            
        Returns:
            list: 筛选后的评论列表
        """
        print(f"\n[3/5] 正在筛选作者ID为 {author_id} 的评论...")
        
        try:
            with open(self.main_comments_file, 'r', encoding='utf-8') as f:
                main_comments = json.load(f)
        except FileNotFoundError:
            print(f"错误: 找不到文件 {self.main_comments_file}")
            sys.exit(1)
        
        # 筛选特定作者的评论
        filtered_comments = [item for item in main_comments if str(item.get('author_id')) == str(author_id)]
        
        if not filtered_comments:
            print(f"警告: 未找到作者ID为 {author_id} 的评论")
            return []
        
        # 保存到文件
        with open(self.filtered_comments_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_comments, f, ensure_ascii=False, indent=2)
        
        print(f"筛选出 {len(filtered_comments)} 条评论到 {self.filtered_comments_file}")
        return filtered_comments
    
    def extract_texts(self, use_filtered=False):
        """
        从评论中提取纯文本内容
        
        Args:
            use_filtered: 是否使用筛选后的评论文件
            
        Returns:
            list: 提取的文本列表
        """
        print(f"\n[4/5] 正在提取文本内容...")
        
        # 选择要使用的JSON文件
        if use_filtered and os.path.exists(self.filtered_comments_file):
            input_file = self.filtered_comments_file
        else:
            input_file = self.main_comments_file
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"错误: 找不到文件 {input_file}")
            sys.exit(1)
        
        # 提取文本内容
        texts = []
        for item in data:
            content = item.get('content', [])
            for part in content:
                if 'text' in part:
                    texts.append(part['text'])
        
        if not texts:
            print("警告: 未提取到任何文本内容")
            return []
        
        # 保存到TXT文件
        with open(self.extracted_texts_file, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(texts))
        
        print(f"提取 {len(texts)} 条文本内容到 {self.extracted_texts_file}")
        return texts
    
    def remove_emoticons(self):
        """
        移除文本中的表情符号
        
        Returns:
            int: 移除的行数
        """
        print(f"\n[5/5] 正在移除表情符号...")
        
        if not os.path.exists(self.extracted_texts_file):
            print(f"错误: 找不到文件 {self.extracted_texts_file}")
            sys.exit(1)
        
        # 读取文件内容
        with open(self.extracted_texts_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 过滤包含"image_emoticon"的行
        filtered_lines = []
        for line in lines:
            if 'image_emoticon' not in line:
                filtered_lines.append(line)
        
        # 写回文件
        with open(self.extracted_texts_file, 'w', encoding='utf-8') as f:
            f.writelines(filtered_lines)
        
        removed_count = len(lines) - len(filtered_lines)
        print(f"移除了 {removed_count} 行包含表情符号的内容")
        print(f"文件已更新: {self.extracted_texts_file}")
        return removed_count
    
    def run(self, har_file, author_id=None, extract_text=False, remove_emoji=False):
        """
        运行完整的提取流程
        
        Args:
            har_file: HAR文件路径
            author_id: 可选，作者ID，用于筛选评论
            extract_text: 是否提取文本内容
            remove_emoji: 是否移除表情符号
        """
        print(f"百度贴吧主楼评论提取器")
        print(f"正在处理文件: {har_file}")
        print("=" * 60)
        
        # 解析HAR文件
        json_files = self.parse_har_file()
        
        # 提取主评论
        self.extract_main_comments(json_files)
        
        # 清理临时文件夹
        shutil.rmtree(self.temp_dir)
        print(f"已清理临时目录: {self.temp_dir}")
        
        # 可选功能：筛选特定作者
        if author_id:
            self.filter_by_author(author_id)
        
        # 可选功能：提取文本内容
        if extract_text:
            self.extract_texts(use_filtered=bool(author_id))
            
            # 可选功能：移除表情符号
            if remove_emoji:
                self.remove_emoticons()
        
        print("\n" + "=" * 60)
        print("提取完成！")


def main():
    """主函数，处理命令行参数"""
    parser = argparse.ArgumentParser(
        description='百度贴吧主楼评论提取器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
1. 基本提取：
   python tieba_comment_extractor.py tieba.baidu.com.har

2. 提取并筛选特定作者：
   python tieba_comment_extractor.py tieba.baidu.com.har --author 6995761944

3. 提取并生成纯文本：
   python tieba_comment_extractor.py tieba.baidu.com.har --extract-text

4. 提取、筛选作者并生成无表情符号的纯文本：
   python tieba_comment_extractor.py tieba.baidu.com.har --author 6995761944 --extract-text --remove-emoji
        """
    )
    
    # 必需参数
    parser.add_argument('har_file', help='HAR文件路径')
    
    # 可选参数
    parser.add_argument('--author', type=str, help='筛选特定作者ID')
    parser.add_argument('--extract-text', action='store_true', help='提取文本内容到TXT文件')
    parser.add_argument('--remove-emoji', action='store_true', help='移除文本中的表情符号')
    
    # 解析参数
    args = parser.parse_args()
    
    # 创建提取器实例并运行
    extractor = TiebaCommentExtractor(args.har_file)
    extractor.run(
        args.har_file,
        author_id=args.author,
        extract_text=args.extract_text,
        remove_emoji=args.remove_emoji
    )


if __name__ == '__main__':
    main()
