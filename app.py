from flask import Flask, request, jsonify, render_template_string
import requests
import concurrent.futures

app = Flask(__name__)

# HTML 模板
HTML_TEMPLATE = """
{% raw %}
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>强者恒强：主升浪龙头猎杀过滤器</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <style>
        body { background-color: #111827; color: #f3f4f6; }
        .table-header { background-color: #1f2937; }
        .row-pass { background-color: rgba(16, 185, 129, 0.1); }
        .row-fail { opacity: 0.7; }
    </style>
</head>
<body class="min-h-screen p-6">
    <div id="app" class="max-w-6xl mx-auto">
        <h1 class="text-3xl font-bold text-red-500 mb-2 flex items-center">
            <span class="mr-2">🐉</span> 强者恒强：主升浪龙头猎杀系统
        </h1>
        <p class="text-gray-400 mb-6">基于腾讯财经接口，严格执行量价、均线、抛压与历史新高过滤逻辑。</p>
        
        <div class="bg-gray-800 rounded-lg p-6 mb-6 shadow-lg border border-gray-700">
            <label class="block text-sm font-medium text-gray-300 mb-2">手动输入代码 (如 sh600519,sz000001)：</label>
            <textarea v-model="stockCodes" rows="2" class="w-full bg-gray-900 border border-gray-600 rounded-md p-3 text-white focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 mb-4 font-mono text-sm"></textarea>
            
            <label class="block text-sm font-medium text-gray-300 mb-2 mt-2">排除代码 (黑名单，如 sh600519,sz000001)，扫描全市场时将排除这些股票：</label>
            <textarea v-model="excludeCodes" rows="1" class="w-full bg-gray-900 border border-gray-600 rounded-md p-3 text-white focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 mb-4 font-mono text-sm"></textarea>

            <div class="flex flex-wrap gap-4">
                <button @click="scanStocks" :disabled="loading" class="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-6 rounded transition-colors flex items-center disabled:opacity-50">
                    <span v-if="loading && scanType==='manual'" class="mr-2 animate-spin">↻</span>
                    {{ (loading && scanType==='manual') ? '正在猎杀中...' : '开始手动扫描' }}
                </button>
                <button @click="scanHotSectors" :disabled="loading" class="bg-yellow-600 hover:bg-yellow-700 text-white font-bold py-2 px-6 rounded transition-colors flex items-center disabled:opacity-50">
                    <span v-if="loading && scanType==='hot'" class="mr-2 animate-spin">↻</span>
                    {{ (loading && scanType==='hot') ? '全市场热门板块猎杀中...' : '一键扫描全市场热门龙头' }}
                </button>
                <button @click="fillHotStocks" class="bg-gray-700 hover:bg-gray-600 text-gray-200 font-bold py-2 px-4 rounded transition-colors">
                    填入预设热门股
                </button>
            </div>
            <div v-if="loading && scanType==='hot'" class="mt-4 text-sm text-yellow-500 animate-pulse">
                正在深度扫描全市场成交额 Top 3000 个股，提取“真龙头”精华（仅展示完全符合条件的 10 只）...
            </div>
        </div>

        <div v-if="results.length > 0" class="bg-gray-800 rounded-lg shadow-lg border border-gray-700 overflow-hidden">
            <div class="p-4 border-b border-gray-700 flex justify-between items-center">
                <h2 class="text-xl font-bold">扫描结果 ({{ results.length }} 只)</h2>
                <div class="text-sm">
                    <span class="text-green-400 font-bold">通过: {{ passedCount }}</span> | 
                    <span class="text-gray-400">淘汰: {{ results.length - passedCount }}</span>
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm">
                    <thead class="table-header text-gray-400">
                        <tr>
                            <th class="p-3">代码</th>
                            <th class="p-3">名称</th>
                            <th class="p-3 text-right">最新价</th>
                            <th class="p-3 text-right">20日均线</th>
                            <th class="p-3 text-right">量比</th>
                            <th class="p-3 text-right">60日新高</th>
                            <th class="p-3 text-center">状态</th>
                            <th class="p-3">过滤原因</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-700">
                        <tr v-for="stock in sortedResults" :key="stock.code" :class="stock.is_dragon_rejected ? 'row-fail' : 'row-pass'">
                            <td class="p-3 font-mono">{{ stock.code }}</td>
                            <td class="p-3 font-bold" :class="stock.is_dragon_rejected ? 'text-gray-300' : 'text-red-400'">{{ stock.name }}</td>
                            <td class="p-3 text-right" :class="stock.price >= stock.open ? 'text-red-500' : 'text-green-500'">{{ stock.price.toFixed(2) }}</td>
                            <td class="p-3 text-right">{{ stock.ma20.toFixed(2) }}</td>
                            <td class="p-3 text-right" :class="stock.vol_ratio >= 2.5 ? 'text-red-500 font-bold' : ''">{{ stock.vol_ratio.toFixed(2) }}</td>
                            <td class="p-3 text-right">{{ stock.max_high_60.toFixed(2) }}</td>
                            <td class="p-3 text-center">
                                <span v-if="!stock.is_dragon_rejected" class="bg-red-900 text-red-200 py-1 px-2 rounded text-xs font-bold border border-red-700">龙头候选</span>
                                <span v-else class="bg-gray-700 text-gray-400 py-1 px-2 rounded text-xs">已淘汰</span>
                            </td>
                            <td class="p-3 text-xs text-gray-400">{{ stock.dragon_reason || '完美符合龙骨形态！' }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const { createApp } = Vue;

        createApp({
            data() {
                return {
                    stockCodes: 'sh600519,sz000001,sh601127,sz002594,sh600036,sz000858,sh601318,sz002475,sh600104,sz002739,sz002281,sz000063',
                    excludeCodes: '',
                    results: [],
                    loading: false,
                    scanType: 'manual'
                }
            },
            computed: {
                passedCount() {
                    return this.results.filter(r => !r.is_dragon_rejected).length;
                },
                sortedResults() {
                    // 把通过的排在前面
                    return [...this.results].sort((a, b) => {
                        if (a.is_dragon_rejected === b.is_dragon_rejected) {
                            return b.vol_ratio - a.vol_ratio; // 同状态按量比排序
                        }
                        return a.is_dragon_rejected ? 1 : -1;
                    });
                }
            },
            methods: {
                fillHotStocks() {
                    this.stockCodes = 'sh600519,sz000001,sh601127,sz002594,sh600036,sz000858,sh601318,sz002475,sh600104,sz002739,sz002281,sz000063,sh603019,sz002230,sh600536,sh601012,sz002241,sz002156,sz002371,sh600418';
                },
                async scanHotSectors() {
                    this.loading = true;
                    this.scanType = 'hot';
                    this.results = [];
                    try {
                        const excludes = this.excludeCodes.split(',').map(c => c.trim()).filter(c => c);
                        const response = await fetch('/api/scan_hot', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ exclude_codes: excludes })
                        });
                        const data = await response.json();
                        if (data.status === 'success') {
                            this.results = data.results;
                        } else {
                            alert("热门扫描出错: " + data.message);
                        }
                    } catch (error) {
                        console.error(error);
                        alert("热门扫描请求失败");
                    } finally {
                        this.loading = false;
                    }
                },
                async scanStocks() {
                    if (!this.stockCodes.trim()) {
                        alert("请输入股票代码");
                        return;
                    }
                    this.loading = true;
                    this.scanType = 'manual';
                    this.results = [];
                    
                    try {
                        const codes = this.stockCodes.split(',').map(c => c.trim()).filter(c => c);
                        const response = await fetch('/api/scan', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ codes: codes })
                        });
                        
                        const data = await response.json();
                        if (data.status === 'success') {
                            this.results = data.results;
                        } else {
                            alert("扫描出错: " + data.message);
                        }
                    } catch (error) {
                        console.error(error);
                        alert("网络请求失败");
                    } finally {
                        this.loading = false;
                    }
                }
            }
        }).mount('#app');
    </script>
</body>
</html>
{% endraw %}
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

def analyze_stock(code):
    try:
        # 使用腾讯财经K线API获取过去60天的日K线数据 (前复权)
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,60,qfq"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        
        if data.get('code') != 0 or code not in data.get('data', {}):
            return {"code": code, "error": "获取数据失败"}
            
        stock_data = data['data'][code]
        # 有时候是 qfqday，有时候是 day (如果没有复权数据)
        kline_key = 'qfqday' if 'qfqday' in stock_data else 'day'
        klines = stock_data.get(kline_key, [])
        
        if not klines or len(klines) < 20:
            return {"code": code, "error": "上市时间不足20天"}
            
        # 解析实时数据或最后一天的数据
        qt_info = stock_data.get('qt', {}).get(code, [])
        if qt_info and len(qt_info) > 3:
            name = qt_info[1]
            price = float(qt_info[3]) # 当前价
            open_price = float(qt_info[5]) # 今开
            high = float(qt_info[33]) # 最高 (或者41, 这里使用实时最高)
            # 为了准确，如果我们使用K线最后一天的最新数据：
            today_kline = klines[-1]
            # K线格式: [date, open, close, high, low, volume]
            # 但如果停牌或未开盘，实时价格可能有变化。我们统一用K线最新一天的数据来计算，以保证一致性。
            today_open = float(today_kline[1])
            today_close = float(today_kline[2])
            today_high = float(today_kline[3])
            today_vol = float(today_kline[5])
            
            # 新增：获取昨日收盘价，计算今日真实涨幅
            yesterday_close = float(klines[-2][2]) if len(klines) >= 2 else today_open
            change_percent = (today_close - yesterday_close) / yesterday_close * 100
        else:
            return {"code": code, "error": "无法获取股票基础信息"}

        # 提取过去20天的收盘价计算MA20
        closes_20 = [float(k[2]) for k in klines[-20:]]
        ma20 = sum(closes_20) / len(closes_20)
        
        # 计算量比 (今天成交量 / 过去5天平均成交量)
        # 过去5天不包含今天（如果今天还在交易中的话，严格来说应取前5天）
        # 这里取 klines[-6:-1] 作为过去5天
        if len(klines) >= 6:
            vols_5 = [float(k[5]) for k in klines[-6:-1]]
            avg_vol_5 = sum(vols_5) / len(vols_5) if sum(vols_5) > 0 else 1
            vol_ratio = today_vol / avg_vol_5
        else:
            vol_ratio = 1.0

        # 计算过去60天的最高价
        highs_60 = [float(k[3]) for k in klines]
        max_high_60 = max(highs_60)

        # ==========================================
        # 核心趋势中军过滤逻辑 (稳健主升浪)
        # ==========================================
        is_dragon_rejected = False
        dragon_reason = ""
        
        price = today_close

        # 1. 基本面排雷：剔除垃圾股和高价股
        if price < 2.0 or price >= 50:
            dragon_reason = "股价极端或超过50元，非稳健资金战场"
            is_dragon_rejected = True
            
        # 1.5 剔除 ST 股
        elif 'ST' in name or 'st' in name:
            dragon_reason = "风险警示股，直接规避"
            is_dragon_rejected = True
        
        # 2. 拒绝涨停板（核心修改！）：
        # 涨幅大于 8% 的直接淘汰，我们不要情绪太亢奋的票，容易冲高回落
        elif change_percent >= 8.0:
            dragon_reason = f"今日涨幅过大({change_percent:.2f}%)，追高风险极大"
            is_dragon_rejected = True

        # 3. 均线通道（核心修改！）：
        # 必须在 MA20 上方，但绝对不能偏离 MA20 太远（限制在 2% ~ 10% 之间）
        elif price < ma20 * 1.02:
            dragon_reason = "走势偏弱，未有效脱离MA20生命线"
            is_dragon_rejected = True
        elif price > ma20 * 1.10:
            dragon_reason = f"偏离MA20过远，随时面临价值回归(乖离率太大)"
            is_dragon_rejected = True
            
        # 4. 温和放量（核心修改！）：
        # 不需要 2.5 倍的极度暴量，1.2 到 2.5 之间最健康，说明有资金稳健建仓
        elif vol_ratio < 1.2:
            dragon_reason = f"量能萎缩，缺乏资金推动(量比{vol_ratio:.2f}<1.2)"
            is_dragon_rejected = True
        elif vol_ratio > 3.0:
            dragon_reason = f"放出天量({vol_ratio:.2f})，筹码松动或主力出逃风险大"
            is_dragon_rejected = True
            
        else:
            # 5. 极端洗盘与抛压过滤（稍微放宽一点点上影线容忍度）
            top_entity = max(today_open, price)
            upper_shadow = today_high - top_entity
            
            if upper_shadow > price * 0.03:
                dragon_reason = "上方遭遇狙击，抛压较重(长上影线)"
                is_dragon_rejected = True
            
            # 6. 蓄势突破（核心修改！）：
            # 不需要非得“创60日新高”，只要距离60日新高在 8% 以内，都在蓄势攻击范围内
            elif price < max_high_60 * 0.92:
                dragon_reason = "距离阶段新高较远，上方套牢盘仍需消化"
                is_dragon_rejected = True

        return {
            "code": code,
            "name": name,
            "price": price,
            "open": today_open,
            "high": today_high,
            "ma20": ma20,
            "vol_ratio": vol_ratio,
            "max_high_60": max_high_60,
            "is_dragon_rejected": is_dragon_rejected,
            "dragon_reason": dragon_reason
        }

    except Exception as e:
        return {"code": code, "error": str(e)}

@app.route('/api/scan', methods=['POST'])
def scan():
    data = request.json
    codes = data.get('codes', [])
    
    if not codes:
        return jsonify({"status": "error", "message": "No codes provided"})
    
    results = []
    # 并发请求腾讯接口加快速度
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(analyze_stock, code): code for code in codes}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if "error" not in res:
                results.append(res)
                
    return jsonify({
        "status": "success",
        "results": results
    })

@app.route('/api/scan_hot', methods=['POST'])
def scan_hot():
    try:
        data = request.json or {}
        exclude_codes = data.get('exclude_codes', [])
        
        # 1. 进一步扩大范围：从新浪财经获取全市场成交额排名前 3000 的个股
        # 分页获取，每页 100 条，取 38 页约 3800 条，几乎涵盖全市场
        all_hot_codes = []
        for page in range(1, 39):
            try:
                url = f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={page}&num=100&sort=amount&asc=0&node=hs_a"
                resp = requests.get(url, timeout=10)
                if not resp.text.strip():
                    break
                
                hot_stocks_raw = resp.json()
                if not hot_stocks_raw:
                    break
                
                if isinstance(hot_stocks_raw, dict) and "__ERROR" in hot_stocks_raw:
                    break
                    
                # 【V4.3升级】：物理隔离 300(创业板) 和 688(科创板) 股票
                page_codes = [
                    s['symbol'] for s in hot_stocks_raw 
                    if isinstance(s, dict) 
                    and 'symbol' in s 
                    and s['symbol'] not in exclude_codes
                    and not s['symbol'].startswith(('sz300', 'sh300', '300', 'sh688', '688'))
                ]
                all_hot_codes.extend(page_codes)
            except Exception as e:
                print(f"获取第 {page} 页热门股票失败: {e}")
                continue
        
        passed_results = []
        
        # 2. 并发分析 (大幅增加线程数以加快全市场扫描)
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(analyze_stock, code): code for code in all_hot_codes}
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if "error" not in res and not res.get('is_dragon_rejected'):
                    passed_results.append(res)
                    # 只要找齐 10 只符合所有条件的票，就可以考虑停止了，但为了“优中选优”，我们还是尽量跑完
        
        # 3. 优中选优：只返回符合条件的票，按量比从高到低排序
        passed_results.sort(key=lambda x: x['vol_ratio'], reverse=True)
        
        # 严格执行：只返回前 20 只符合条件的
        final_list = passed_results[:20]

        return jsonify({
            "status": "success",
            "results": final_list
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
