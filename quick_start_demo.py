# -*- coding: utf-8 -*-
import os
import sys

# 兼容 Windows 命令行 Unicode 字符打印（如音标中的国际音标）
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from stardict import DictCsv, LemmaDB

def main():
    # 获取当前脚本所在目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. 演示使用 DictCsv 读取 ecdict.mini.csv
    csv_file = os.path.join(base_dir, 'ecdict.mini.csv')
    print("正在加载词典数据 %s..." % csv_file)
    dct = DictCsv(csv_file)
    print("词典加载完毕，共收录 %d 个词条。\n" % len(dct))
    
    # 测试查询单词
    test_words = ['why not', 'inconsequent', 'nite']
    print("=================== 单词查询演示 ===================")
    for word in test_words:
        result = dct.query(word)
        if result:
            print("【单词】: %s" % result.get('word'))
            print("【音标】: %s" % result.get('phonetic', ''))
            print("【翻译】:\n%s" % result.get('translation', ''))
            print("【词性】: %s" % result.get('pos', ''))
            print("【时态变换】: %s" % result.get('exchange', ''))
            print("-" * 50)
        else:
            print("未找到单词: %s" % word)
            print("-" * 50)
            
    # 2. 演示 LemmaDB 词干还原
    lemma_file = os.path.join(base_dir, 'lemma.en.txt')
    if os.path.exists(lemma_file):
        print("\n=================== 词干还原演示 ===================")
        print("正在加载词干还原数据库 %s..." % lemma_file)
        ldb = LemmaDB()
        ldb.load(lemma_file)
        print("还原库加载完毕，共收录 %d 个词形关系。\n" % len(ldb))
        
        # 测试词形还原
        # 'took' 的原型通常是 'take'，'gave' 的原型是 'give'
        test_stems = ['took', 'gave', 'unshipped', 'unshipping']
        for w in test_stems:
            stems = ldb.word_stem(w)
            if stems:
                print("【变形】: %s  ==还原原型==>  【原型】: %s" % (w, ', '.join(stems)))
            else:
                print("【变形】: %s  ==还原原型==>  【原型】: 未找到原型（返回 None）" % w)
            
if __name__ == '__main__':
    main()
