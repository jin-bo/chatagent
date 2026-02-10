#!/usr/bin/env python3
"""
科研WBS审核脚本
基于标准化原则审核科研项目WBS Excel表格
"""

import pandas as pd
import sys
import json
from typing import Dict, List, Tuple
from collections import defaultdict

class WBSReviewer:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.issues = defaultdict(list)
        self.df = None
        self.load_wbs()

    def load_wbs(self):
        """加载WBS文件"""
        try:
            df_raw = pd.read_excel(self.file_path, sheet_name='WBS', skiprows=3)

            # 找到实际的列标题行（第一行非空行）
            header_row = None
            for idx, row in df_raw.iterrows():
                if pd.notna(row[2]) and row[2] == 'WBS':
                    header_row = idx
                    break

            if header_row is not None:
                # 重新读取，使用找到的标题行
                df = pd.read_excel(self.file_path, sheet_name='WBS', skiprows=3+header_row+1,
                                   names=['_', 'Level', 'WBS', 'Task Description', 'Type', 'Priority',
                                          'Assigned To', 'Status', 'Start', 'End', '今天进展', '明天计划', 'Notes'])
                self.df = df
            else:
                # 使用原始读取，自行设置列名
                self.df = df_raw
                self.df.columns = ['_', 'Level', 'WBS', 'Task Description', 'Type', 'Priority',
                                   'Assigned To', 'Status', 'Start', 'End', '今天进展', '明天计划', 'Notes']
                # 跳过标题行
                self.df = self.df[self.df['WBS'].notna() & (self.df['WBS'] != 'WBS')]

            # 读取字典sheet获取允许的值
            self.dict_df = pd.read_excel(self.file_path, sheet_name='Dictionary')

        except Exception as e:
            raise Exception(f"无法读取WBS文件: {e}")

    def check_classification_principle(self):
        """检查分类组合原则"""
        # 检查Type字段是否规范
        valid_types = ['目标', '里程碑', '正常', '低风险', '中风险', '高风险']

        for idx, row in self.df.iterrows():
            wbs_code = row['WBS']
            wbe_type = row['Type']
            task_desc = row['Task Description']

            # Level 1项必须有Type且为"目标"
            if row['Level'] == 1:
                if pd.isna(wbe_type):
                    self.issues['分类组合'].append({
                        'row': idx + 5,  # 调整行号
                        'wbs': wbs_code,
                        'severity': '高',
                        'issue': f'一级WBE "{task_desc}" 缺少Type字段',
                        'suggestion': '一级WBE必须标记为"目标"类型，代表可交付成果'
                    })
                elif wbe_type != '目标':
                    self.issues['分类组合'].append({
                        'row': idx + 5,
                        'wbs': wbs_code,
                        'severity': '中',
                        'issue': f'一级WBE "{task_desc}" 的Type为 "{wbe_type}"，不是"目标"',
                        'suggestion': '一级WBE应标记为"目标"类型，表示可交付的WBE'
                    })

            # 检查Type是否在允许范围内
            if pd.notna(wbe_type) and wbe_type not in valid_types:
                self.issues['分类组合'].append({
                    'row': idx + 5,
                    'wbs': wbs_code,
                    'severity': '中',
                    'issue': f'WBE "{task_desc}" 的Type "{wbe_type}" 不在标准类型中',
                    'suggestion': f'Type应为以下之一: {", ".join(valid_types)}'
                })

    def check_goal_clarity_principle(self):
        """检查厘清目标原则"""
        for idx, row in self.df.iterrows():
            wbs_code = row['WBS']
            task_desc = row['Task Description']
            level = row['Level']

            # 检查任务描述是否清晰
            if pd.isna(task_desc) or str(task_desc).strip() == '':
                self.issues['厘清目标'].append({
                    'row': idx + 5,
                    'wbs': wbs_code,
                    'severity': '高',
                    'issue': f'WBS编号 {wbs_code} 缺少任务描述',
                    'suggestion': '必须明确描述WBE的交付内容和预期目标'
                })

            # 一级WBE应明确说明交付物类型
            if level == 1:
                deliverable_keywords = ['交付物', '系统', '产品', '报告', '数据集', '测试集', '标准', '课题']
                has_deliverable = any(kw in str(task_desc) for kw in deliverable_keywords)

                if not has_deliverable:
                    self.issues['厘清目标'].append({
                        'row': idx + 5,
                        'wbs': wbs_code,
                        'severity': '中',
                        'issue': f'一级WBE "{task_desc}" 未明确说明交付物类型',
                        'suggestion': '建议在描述中包含"交付物-"前缀，如：交付物-系统/产品、交付物-报告、交付物-数据集等'
                    })

            # 检查开始和结束日期
            if level == 1 or pd.notna(row['Assigned To']):
                if pd.isna(row['Start']):
                    self.issues['厘清目标'].append({
                        'row': idx + 5,
                        'wbs': wbs_code,
                        'severity': '中',
                        'issue': f'WBE "{task_desc}" 缺少开始日期',
                        'suggestion': '有责任人的WBE应明确时间节点'
                    })
                if pd.isna(row['End']) and row['Status'] != '进行中':
                    self.issues['厘清目标'].append({
                        'row': idx + 5,
                        'wbs': wbs_code,
                        'severity': '中',
                        'issue': f'WBE "{task_desc}" 缺少结束日期',
                        'suggestion': '应明确完成时间以便进度跟踪'
                    })

    def check_mutual_confirmation_principle(self):
        """检查双方确认原则"""
        # 检查是否有明确的责任人
        unassigned_level1 = []

        for idx, row in self.df.iterrows():
            if row['Level'] == 1:
                assigned_to = row['Assigned To']
                task_desc = row['Task Description']

                if pd.isna(assigned_to):
                    unassigned_level1.append({
                        'row': idx + 5,
                        'wbs': row['WBS'],
                        'task': task_desc
                    })

        if unassigned_level1:
            for item in unassigned_level1:
                self.issues['双方确认'].append({
                    'row': item['row'],
                    'wbs': item['wbs'],
                    'severity': '高',
                    'issue': f'一级WBE "{item["task"]}" 未分配责任人',
                    'suggestion': '所有一级WBE必须明确责任单位/团队，确保双方确认责任边界'
                })

    def check_responsibility_matching_principle(self):
        """检查责任匹配原则"""
        # 检查责任颗粒度
        for idx, row in self.df.iterrows():
            wbs_code = row['WBS']
            assigned_to = row['Assigned To']
            task_desc = row['Task Description']
            level = row['Level']

            # 叶子节点应有明确责任人
            next_idx = idx + 1
            is_leaf = True
            if next_idx < len(self.df):
                next_level = self.df.iloc[next_idx]['Level']
                if next_level > level:
                    is_leaf = False

            if is_leaf and level > 1:
                if pd.isna(assigned_to):
                    self.issues['责任匹配'].append({
                        'row': idx + 5,
                        'wbs': wbs_code,
                        'severity': '中',
                        'issue': f'叶子节点WBE "{task_desc}" (Level {level}) 未分配责任人',
                        'suggestion': '最底层可执行的WBE应明确责任人，确保可追责'
                    })

            # 检查是否有重复责任人在同一父节点下的兄弟节点
            # (简化检查：统计同一负责人承担的一级WBE数量)
            if level == 1 and pd.notna(assigned_to):
                count = len(self.df[(self.df['Level'] == 1) & (self.df['Assigned To'] == assigned_to)])
                if count > 3:
                    self.issues['责任匹配'].append({
                        'row': idx + 5,
                        'wbs': wbs_code,
                        'severity': '低',
                        'issue': f'责任人 "{assigned_to}" 承担了 {count} 个一级WBE',
                        'suggestion': '建议评估工作量是否合理，必要时重新分配'
                    })

    def check_wbs_structure(self):
        """检查WBS结构完整性"""
        # 检查WBS编号的层级关系
        prev_code = None
        for idx, row in self.df.iterrows():
            wbs_code = str(row['WBS'])
            level = row['Level']

            # 检查Level与WBS编号的层级是否匹配
            code_level = wbs_code.count('.') + 1
            if code_level != level:
                self.issues['结构完整性'].append({
                    'row': idx + 5,
                    'wbs': wbs_code,
                    'severity': '高',
                    'issue': f'WBS编号 {wbs_code} 的层级数({code_level})与Level字段({level})不匹配',
                    'suggestion': f'WBS编号应为 {level} 层结构'
                })

    def check_status_consistency(self):
        """检查状态一致性"""
        valid_statuses = ['未分配', '未开始', '进行中', '延误', '完成']

        for idx, row in self.df.iterrows():
            status = row['Status']
            task_desc = row['Task Description']
            wbs_code = row['WBS']

            if pd.notna(status) and status not in valid_statuses:
                self.issues['状态一致性'].append({
                    'row': idx + 5,
                    'wbs': wbs_code,
                    'severity': '低',
                    'issue': f'WBE "{task_desc}" 的状态 "{status}" 不在标准状态列表中',
                    'suggestion': f'状态应为: {", ".join(valid_statuses)}'
                })

            # 已完成的任务应该有结束日期
            if status == '完成' and pd.isna(row['End']):
                self.issues['状态一致性'].append({
                    'row': idx + 5,
                    'wbs': wbs_code,
                    'severity': '中',
                    'issue': f'WBE "{task_desc}" 标记为完成但缺少结束日期',
                    'suggestion': '已完成的任务应记录实际完成日期'
                })

    def generate_report(self) -> str:
        """生成审核报告"""
        report = []
        report.append("# 科研WBS审核报告\n")
        report.append(f"**审核文件**: {self.file_path}\n")
        report.append(f"**WBE总数**: {len(self.df)}\n")

        # 统计问题
        total_issues = sum(len(issues) for issues in self.issues.values())
        report.append(f"**发现问题**: {total_issues} 个\n")

        if total_issues == 0:
            report.append("\n✅ **审核通过！WBS结构符合标准要求。**\n")
            return '\n'.join(report)

        # 按严重程度统计
        severity_count = {'高': 0, '中': 0, '低': 0}
        for issues in self.issues.values():
            for issue in issues:
                severity_count[issue['severity']] += 1

        report.append(f"- 高严重度: {severity_count['高']} 个")
        report.append(f"- 中严重度: {severity_count['中']} 个")
        report.append(f"- 低严重度: {severity_count['低']} 个\n")

        # 详细问题列表
        report.append("---\n")
        report.append("## 审核详情\n")

        principles = [
            ('分类组合', '分类组合原则'),
            ('厘清目标', '厘清目标原则'),
            ('双方确认', '双方确认原则'),
            ('责任匹配', '责任匹配原则'),
            ('结构完整性', 'WBS结构完整性'),
            ('状态一致性', '状态一致性检查')
        ]

        for key, title in principles:
            if key in self.issues and self.issues[key]:
                report.append(f"### {title}\n")

                for issue in sorted(self.issues[key], key=lambda x: x['severity'], reverse=True):
                    severity_emoji = {'高': '🔴', '中': '🟡', '低': '🟢'}
                    report.append(f"#### {severity_emoji[issue['severity']]} 行 {issue['row']} - WBS {issue['wbs']}\n")
                    report.append(f"**问题**: {issue['issue']}\n")
                    report.append(f"**建议**: {issue['suggestion']}\n")

                report.append("")

        return '\n'.join(report)

    def review(self) -> str:
        """执行完整审核"""
        self.check_classification_principle()
        self.check_goal_clarity_principle()
        self.check_mutual_confirmation_principle()
        self.check_responsibility_matching_principle()
        self.check_wbs_structure()
        self.check_status_consistency()

        return self.generate_report()


def main():
    if len(sys.argv) < 2:
        print("用法: python review_wbs.py <WBS文件路径>")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        reviewer = WBSReviewer(file_path)
        report = reviewer.review()
        print(report)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
