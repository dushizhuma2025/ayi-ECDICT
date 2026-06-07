# -*- coding: utf-8 -*-
import os
import sys
import json
import sqlite3
import urllib.parse
import re
from http.server import HTTPServer, BaseHTTPRequestHandler

# 兼容 Windows 命令行 Unicode 字符打印
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import webbrowser
import threading
import time

def get_resource_path(relative_path):
    """获取打包在 exe 内部的静态文件绝对路径 (兼容 PyInstaller 临时释放目录)"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_workspace_path(relative_path):
    """获取与 exe 处于同级目录的工作区文件绝对路径"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

PORT = 8000
DB_FILE = get_workspace_path('ecdict.db')
CSV_FILE = get_workspace_path('ecdict.csv')

def extract_pos(translation):
    """从中文释义中智能提取词性缩写标签"""
    if not translation:
        return ""
    # 按换行符切分多行释义
    lines = re.split(r'\n|\\n', translation)
    found_pos = []
    for line in lines:
        line = line.strip()
        # 匹配行首字母接圆点，例如 "n.", "adj.", "vt."
        m = re.match(r'^([a-zA-Z]+)\.', line)
        if m:
            pos_tag = m.group(1).lower()
            # 过滤非标准前缀（限制长度在5位以内）
            if len(pos_tag) <= 5 and pos_tag not in found_pos:
                found_pos.append(pos_tag)
    return "/".join(found_pos)

def format_pos(pos):
    """格式化词性：使每个词性缩写以 '.' 结尾，并且用 ' / ' 隔开"""
    if not pos:
        return ""
    parts = [p.strip() for p in re.split(r'\/| / ', pos) if p.strip()]
    formatted = []
    for p in parts:
        if not p.endswith('.'):
            p = p + '.'
        formatted.append(p)
    return " / ".join(formatted)

def init_database():
    """检测并转换数据库，同时建立索引"""
    if not os.path.exists(DB_FILE):
        print("未检测到本地数据库 %s，正在从 %s 转换生成（这可能需要大约 1 分钟，请稍候）..." % (DB_FILE, CSV_FILE))
        import stardict
        stardict.convert_dict(DB_FILE, CSV_FILE)
        print("数据库转换完成！")
        
    # 建立多维筛选字段的索引以实现毫秒级响应
    print("检查并建立数据库索引...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_collins ON stardict(collins);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_oxford ON stardict(oxford);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tag ON stardict(tag);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bnc ON stardict(bnc);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_frq ON stardict(frq);')
    conn.commit()
    conn.close()
    print("数据库已就绪！")

class WordExplorerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # 1. 静态资源托管
        if path == "/" or path == "/index.html":
            self.serve_file('index.html', 'text/html')
        elif path == "/index.css":
            self.serve_file('index.css', 'text/css')
        elif path == "/index.js":
            self.serve_file('index.js', 'application/javascript')
        
        # 2. RESTful API 接口
        elif path == "/api/words":
            self.handle_api_words(urllib.parse.parse_qs(parsed_url.query))
        elif path == "/api/words/export":
            self.handle_api_words_export(urllib.parse.parse_qs(parsed_url.query))
            
        else:
            self.send_error(404, "File Not Found")

    def serve_file(self, filename, content_type):
        filepath = get_resource_path(filename)
        if not os.path.exists(filepath):
            self.send_error(404, "File %s Not Found" % filename)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        with open(filepath, 'rb') as f:
            self.wfile.write(f.read())

    def handle_api_words(self, params):
        # 提取参数并做健壮性转换
        try:
            page = int(params.get('page', ['1'])[0])
            limit = int(params.get('limit', ['20'])[0])
        except ValueError:
            page, limit = 1, 20
            
        limit = min(max(limit, 5), 100) # 限制单页最大100条
        offset = (page - 1) * limit
        
        word_query = params.get('word', [''])[0].strip()
        collins = params.get('collins', [''])[0].strip()
        oxford = params.get('oxford', [''])[0].strip()
        tag = params.get('tag', [''])[0].strip()
        
        bnc_min = params.get('bnc_min', [''])[0].strip()
        bnc_max = params.get('bnc_max', [''])[0].strip()
        frq_min = params.get('frq_min', [''])[0].strip()
        frq_max = params.get('frq_max', [''])[0].strip()
        sort_by = params.get('sort_by', [''])[0].strip().lower()

        # 构建 SQL WHERE 语句
        conditions = []
        sql_params = []
        
        if word_query:
            conditions.append("word LIKE ?")
            sql_params.append(word_query + "%")
        if collins:
            try:
                val = int(collins)
                if val == 0:
                    conditions.append("(collins = 0 OR collins IS NULL)")
                else:
                    conditions.append("collins >= ?")
                    sql_params.append(val)
            except ValueError:
                pass
        if oxford:
            try:
                conditions.append("oxford = ?")
                sql_params.append(int(oxford))
            except ValueError:
                pass
        if tag:
            conditions.append("tag LIKE ?")
            sql_params.append("%" + tag + "%")
        if bnc_min:
            try:
                conditions.append("bnc >= ?")
                sql_params.append(int(bnc_min))
            except ValueError:
                pass
        if bnc_max:
            try:
                conditions.append("bnc <= ?")
                sql_params.append(int(bnc_max))
            except ValueError:
                pass
        if frq_min:
            try:
                conditions.append("frq >= ?")
                sql_params.append(int(frq_min))
            except ValueError:
                pass
        if frq_max:
            try:
                conditions.append("frq <= ?")
                sql_params.append(int(frq_max))
            except ValueError:
                pass

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # 排序处理
        valid_sort_fields = {
            "bnc": "bnc",
            "coca": "frq",
            "collins": "collins"
        }
        sort_clause = ""
        if sort_by in valid_sort_fields:
            db_field = valid_sort_fields[sort_by]
            # bnc 和 coca (frq) 是数值越小词频越高，所以使用升序 ASC 排序
            direction = "ASC" if sort_by in ("bnc", "coca") else "DESC"
            sort_clause = f" ORDER BY CASE WHEN {db_field} IS NULL OR {db_field} = 0 THEN 0 ELSE 1 END DESC, {db_field} {direction}"
        else:
            sort_clause = " ORDER BY word ASC"
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 查询总条数
        count_sql = "SELECT COUNT(*) FROM stardict" + where_clause
        cursor.execute(count_sql, tuple(sql_params))
        total = cursor.fetchone()[0]
        
        # 查询数据
        data_sql = "SELECT id, word, phonetic, translation, definition, pos, collins, oxford, tag, bnc, frq, exchange FROM stardict" + where_clause + sort_clause + " LIMIT ? OFFSET ?"
        cursor.execute(data_sql, tuple(sql_params + [limit, offset]))
        rows = cursor.fetchall()
        
        # 封装结果
        words_list = []
        for r in rows:
            pos = r[5] or ""
            translation = r[3] or ""
            # 若数据库中 pos 为空且释义存在，则通过释义补全词性
            if not pos and translation:
                pos = extract_pos(translation)
            pos = format_pos(pos)
                
            words_list.append({
                "id": r[0],
                "word": r[1],
                "phonetic": r[2] or "",
                "translation": translation,
                "definition": r[4] or "",
                "pos": pos,
                "collins": r[6] or 0,
                "oxford": r[7] or 0,
                "tag": r[8] or "",
                "bnc": r[9],
                "frq": r[10],
                "exchange": r[11] or ""
            })
            
        conn.close()
        
        response_data = {
            "success": True,
            "total": total,
            "page": page,
            "limit": limit,
            "data": words_list
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))

    def handle_api_words_export(self, params):
        # 1. 提取参数
        word_query = params.get('word', [''])[0].strip()
        collins = params.get('collins', [''])[0].strip()
        oxford = params.get('oxford', [''])[0].strip()
        tag = params.get('tag', [''])[0].strip()
        
        bnc_min = params.get('bnc_min', [''])[0].strip()
        bnc_max = params.get('bnc_max', [''])[0].strip()
        frq_min = params.get('frq_min', [''])[0].strip()
        frq_max = params.get('frq_max', [''])[0].strip()
        sort_by = params.get('sort_by', [''])[0].strip().lower()

        # 构建 SQL WHERE 语句
        conditions = []
        sql_params = []
        
        if word_query:
            conditions.append("word LIKE ?")
            sql_params.append(word_query + "%")
        if collins:
            try:
                val = int(collins)
                if val == 0:
                    conditions.append("(collins = 0 OR collins IS NULL)")
                else:
                    conditions.append("collins >= ?")
                    sql_params.append(val)
            except ValueError:
                pass
        if oxford:
            try:
                conditions.append("oxford = ?")
                sql_params.append(int(oxford))
            except ValueError:
                pass
        if tag:
            conditions.append("tag LIKE ?")
            sql_params.append("%" + tag + "%")
        if bnc_min:
            try:
                conditions.append("bnc >= ?")
                sql_params.append(int(bnc_min))
            except ValueError:
                pass
        if bnc_max:
            try:
                conditions.append("bnc <= ?")
                sql_params.append(int(bnc_max))
            except ValueError:
                pass
        if frq_min:
            try:
                conditions.append("frq >= ?")
                sql_params.append(int(frq_min))
            except ValueError:
                pass
        if frq_max:
            try:
                conditions.append("frq <= ?")
                sql_params.append(int(frq_max))
            except ValueError:
                pass

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # 排序处理
        valid_sort_fields = {
            "bnc": "bnc",
            "coca": "frq",
            "collins": "collins"
        }
        sort_clause = ""
        if sort_by in valid_sort_fields:
            db_field = valid_sort_fields[sort_by]
            # bnc 和 coca (frq) 是数值越小词频越高，所以使用升序 ASC 排序
            direction = "ASC" if sort_by in ("bnc", "coca") else "DESC"
            sort_clause = f" ORDER BY CASE WHEN {db_field} IS NULL OR {db_field} = 0 THEN 0 ELSE 1 END DESC, {db_field} {direction}"
        else:
            sort_clause = " ORDER BY word ASC"
            
        limit = 5000
        data_sql = "SELECT word, phonetic, pos, definition, translation FROM stardict" + where_clause + sort_clause + " LIMIT ?"
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(data_sql, tuple(sql_params + [limit]))
        rows = cursor.fetchall()
        conn.close()

        # 3. 构造 CSV 字节数据
        import io
        import csv
        
        output = io.StringIO()
        writer = csv.writer(output, lineterminator='\n')
        
        # 写入表头
        writer.writerow(["所在单元", "词条", "音标", "词性", "英文释义", "中文释义", "例句", "例句翻译"])
        
        for i, r in enumerate(rows, 1):
            unit = (i - 1) // 10 + 1
            word = r[0]
            phonetic = r[1] or ""
            # 清洗音标，剥离外围的中括号
            phonetic = phonetic.strip('[]')
            
            pos = r[2] or ""
            definition = r[3] or ""
            translation = r[4] or ""
            # 若导出时 pos 字段为空，通过释义补充词性列
            if not pos and translation:
                pos = extract_pos(translation)
            pos = format_pos(pos)
                
            example = ""
            example_trans = ""
            
            writer.writerow([unit, word, phonetic, pos, definition, translation, example, example_trans])
            
        csv_data = output.getvalue()
        output.close()
        
        # 使用 带 BOM 的 UTF-8 编码，防止 Excel 乱码
        bom_bytes = b'\xef\xbb\xbf'
        response_bytes = bom_bytes + csv_data.encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename="ecdict_export.csv"')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response_bytes)

def open_browser():
    """等待服务器完全启动后调起默认浏览器打开页面"""
    time.sleep(1.0)
    webbrowser.open("http://localhost:8000")

def run():
    init_database()
    # 启动后台线程以自动调起默认浏览器
    threading.Thread(target=open_browser, daemon=True).start()
    
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, WordExplorerHandler)
    print("ECDICT 单词浏览器已在后台运行！打开本地访问地址：http://localhost:%d" % PORT)
    httpd.serve_forever()

if __name__ == '__main__':
    run()
