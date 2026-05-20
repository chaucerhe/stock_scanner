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
    <title>伏击圈：精准回踩猎杀过滤器</title> 
    <script src="https://cdn.tailwindcss.com"></script> 
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script> 
    <style> 
        body { background-color: #0f172a; color: #f8fafc; } /* 深蓝灰背景，更冷静 */ 
        .table-header { background-color: #1e293b; } 
        .row-pass { background-color: rgba(56, 189, 248, 0.1); } /* 冰蓝色，代表冷静潜伏 */ 
        .row-fail { opacity: 0.6; } 
    </style> 
</head> 
<body class="min-h-screen p-6"> 
    <div id="app" class="max-w-6xl mx-auto"> 
        <h1 class="text-3xl font-bold text-cyan-400 mb-2 flex items-center"> 
            <span class="mr-2">🎯</span> 伏击圈：精准缩量回踩猎杀系统 
        </h1> 
        <p class="text-slate-400 mb-6">核心纪律：不追高、等缩量、踩均线。专治手痒，只做右侧确定性低吸。</p> 
        
        <div class="bg-slate-800 rounded-lg p-6 mb-6 shadow-lg border border-slate-700"> 
            <label class="block text-sm font-medium text-slate-300 mb-2">手动输入代码 (如 sh600519,sz000001)：</label> 
            <textarea v-model="stockCodes" rows="2" class="w-full bg-slate-900 border border-slate-600 rounded-md p-3 text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 mb-4 font-mono text-sm"></textarea> 
            
            <label class="block text-sm font-medium text-slate-300 mb-2 mt-2">排除代码 (黑名单)：</label> 
            <textarea v-model="excludeCodes" rows="1" class="w-full bg-slate-900 border border-slate-600 rounded-md p-3 text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 mb-4 font-mono text-sm"></textarea> 
 
            <div class="flex flex-wrap gap-4"> 
                <button @click="scanStocks" :disabled="loading" class="bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-2 px-6 rounded transition-colors flex items-center disabled:opacity-50 shadow-[0_0_10px_rgba(8,145,178,0.5)]"> 
                    <span v-if="loading && scanType==='manual'" class="mr-2 animate-spin">↻</span> 
                    {{ (loading && scanType==='manual') ? '深度测算中...' : '开始手动扫描' }} 
                </button> 
                <button @click="scanHotSectors" :disabled="loading" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-6 rounded transition-colors flex items-center disabled:opacity-50"> 
                    <span v-if="loading && scanType==='hot'" class="mr-2 animate-spin">↻</span> 
                    {{ (loading && scanType==='hot') ? '全市场地雷阵铺设中...' : '一键扫描全市场黄金坑' }} 
                </button> 
                <button @click="fillHotStocks" class="bg-slate-700 hover:bg-slate-600 text-slate-200 font-bold py-2 px-4 rounded transition-colors"> 
                    填入自选股观察池 
                </button> 
            </div> 
            <div v-if="loading && scanType==='hot'" class="mt-4 text-sm text-cyan-500 animate-pulse"> 
                正在深度扫描全市场，过滤暴涨妖股，寻找完美贴合 20 日均线的“熟睡中军”... 
            </div> 
        </div> 
 
        <div v-if="results.length > 0" class="bg-slate-800 rounded-lg shadow-lg border border-slate-700 overflow-hidden"> 
            <div class="p-4 border-b border-slate-700 flex justify-between items-center"> 
                <h2 class="text-xl font-bold text-slate-100">伏击雷达结果 ({{ results.length }} 只)</h2> 
                <div class="text-sm"> 
                    <span class="text-cyan-400 font-bold">完美回踩: {{ passedCount }}</span> | 
                    <span class="text-slate-400">形态破坏: {{ results.length - passedCount }}</span> 
                </div> 
            </div> 
            <div class="overflow-x-auto"> 
                <table class="w-full text-left text-sm"> 
                    <thead class="table-header text-slate-400"> 
                        <tr> 
                            <th class="p-3">代码</th> 
                            <th class="p-3">名称</th> 
                            <th class="p-3 text-right">最新价</th> 
                            <th class="p-3 text-right">MA20防线</th> 
                            <th class="p-3 text-right">均线乖离率</th> 
                            <th class="p-3 text-right">量比(需极度缩量)</th> 
                            <th class="p-3 text-center">状态</th> 
                            <th class="p-3">系统判定</th> 
                        </tr> 
                    </thead> 
                    <tbody class="divide-y divide-slate-700"> 
                        <tr v-for="stock in sortedResults" :key="stock.code" :class="stock.is_rejected ? 'row-fail' : 'row-pass'"> 
                            <td class="p-3 font-mono text-slate-300">{{ stock.code }}</td> 
                            <td class="p-3 font-bold" :class="stock.is_rejected ? 'text-slate-500' : 'text-cyan-400'">{{ stock.name }}</td> 
                            <td class="p-3 text-right" :class="stock.change_percent > 0 ? 'text-red-400' : 'text-green-400'">{{ stock.price.toFixed(2) }}</td> 
                            <td class="p-3 text-right text-slate-300">{{ stock.ma20.toFixed(2) }}</td> 
                            <td class="p-3 text-right font-mono" :class="abs(stock.bias_20) <= 2 ? 'text-cyan-400 font-bold' : 'text-slate-400'">{{ stock.bias_20 > 0 ? '+' : '' }}{{ stock.bias_20.toFixed(2) }}%</td> 
                            <td class="p-3 text-right" :class="stock.vol_ratio <= 0.8 ? 'text-cyan-400 font-bold' : 'text-slate-400'">{{ stock.vol_ratio.toFixed(2) }}</td> 
                            <td class="p-3 text-center"> 
                                <span v-if="!stock.is_rejected" class="bg-cyan-900 text-cyan-200 py-1 px-2 rounded text-xs font-bold border border-cyan-700">进入伏击圈</span> 
                                <span v-else class="bg-slate-700 text-slate-400 py-1 px-2 rounded text-xs">观望</span> 
                            </td> 
                            <td class="p-3 text-xs text-slate-400">{{ stock.reject_reason || '已踩中20日均线，缩量企稳，可择机埋伏！' }}</td> 
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
                    stockCodes: 'sh600023,sz000027,sz000899,sh605020', 
                    excludeCodes: 'sz000899', // 默认把渣男股屏蔽 
                    results: [], 
                    loading: false, 
                    scanType: 'manual' 
                } 
            }, 
            computed: { 
                passedCount() { 
                    return this.results.filter(r => !r.is_rejected).length; 
                }, 
                sortedResults() { 
                    return [...this.results].sort((a, b) => { 
                        if (a.is_rejected === b.is_rejected) { 
                            return Math.abs(a.bias_20) - Math.abs(b.bias_20); // 同状态下，乖离率越接近0越排前面 
                        } 
                        return a.is_rejected ? 1 : -1; 
                    }); 
                } 
            }, 
            methods: { 
                abs(val) { return Math.abs(val); }, 
                fillHotStocks() { 
                    this.stockCodes = 'sh600023,sz000027,sz000899,sh605020,sh600900,sz000001,sh601318'; 
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
                            alert("扫描出错: " + data.message); 
                        } 
                    } catch (error) { 
                        console.error(error); 
                        alert("网络请求失败"); 
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
 
def analyze_stock_pullback(code): 
    try: 
        # ==== 【升级1】彻底治好近视眼，强制获取过去 250 天（一年）的数据！ ==== 
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,250,qfq" 
        resp = requests.get(url, timeout=5) 
        data = resp.json() 
        
        if data.get('code') != 0 or code not in data.get('data', {}): 
            return {"code": code, "error": "获取数据失败"} 
            
        stock_data = data['data'][code] 
        kline_key = 'qfqday' if 'qfqday' in stock_data else 'day' 
        klines = stock_data.get(kline_key, []) 
        
        # 必须上市超过半年才能判断大趋势 
        if not klines or len(klines) < 120: 
            return {"code": code, "error": "上市不足半年，缺乏长线支撑参考"} 
            
        qt_info = stock_data.get('qt', {}).get(code, []) 
        if qt_info and len(qt_info) > 3: 
            name = qt_info[1] 
            today_kline = klines[-1] 
            today_open = float(today_kline[1]) 
            today_close = float(today_kline[2]) 
            today_high = float(today_kline[3]) 
            today_low = float(today_kline[4]) 
            today_vol = float(today_kline[5]) 
            
            yesterday_close = float(klines[-2][2]) 
            change_percent = (today_close - yesterday_close) / yesterday_close * 100 
        else: 
            return {"code": code, "error": "无法获取实时数据"} 
 
        # ==== 【升级2】增加半年线(120日)和半年新高的测算 ==== 
        highs_120 = [float(k[3]) for k in klines[-120:]] 
        max_high_120 = max(highs_120) 

        # ==== 均线计算部分：新增昨天和前天的 MA20，用来计算斜率和趋势稳定性 ==== 
        closes_21 = [float(k[2]) for k in klines[-21:]] 
        ma20 = sum(closes_21[-20:]) / 20 
        ma20_yesterday = sum(closes_21[-21:-1]) / 20 
        
        # ==== V4.1 新增：计算 MA5, MA10, MA30 用于过滤死结和头顶铡刀 ==== 
        closes_5 = [float(k[2]) for k in klines[-5:]] 
        ma5 = sum(closes_5) / 5 
        
        closes_10 = [float(k[2]) for k in klines[-10:]] 
        ma10 = sum(closes_10) / 10 
 
        closes_30 = [float(k[2]) for k in klines[-30:]] 
        ma30 = sum(closes_30) / max(1, len(closes_30)) 
        
        closes_60 = [float(k[2]) for k in klines[-60:]] 
        ma60 = sum(closes_60) / len(closes_60) 

        closes_120 = [float(k[2]) for k in klines[-120:]] 
        ma120 = sum(closes_120) / len(closes_120) 
 
        # 量比计算 
        vols_5 = [float(k[5]) for k in klines[-6:-1]] 
        avg_vol_5 = sum(vols_5) / len(vols_5) if sum(vols_5) > 0 else 1 
        vol_ratio = today_vol / avg_vol_5 
 
        # 乖离率计算 
        bias_20 = (today_close - ma20) / ma20 * 100 
 
        # ========================================== 
        # 核心：精准回踩过滤逻辑 (冷血狙击手模式 V4.0 - 金身不坏版) 
        # ========================================== 
        is_rejected = False 
        reject_reason = "" 
        
        price = today_close 

        # 0. 【新增：价格限制】只做 50 元以下的股票
        if price >= 50:
            reject_reason = "价格过高：当前股价超过或等于50元，放弃"
            is_rejected = True
            
        # 0.5 剔除 ST 股
        elif 'ST' in name or 'st' in name:
            reject_reason = "风险警示股，直接规避"
            is_rejected = True

        # 1. 【新增：绝对支撑红线】拒绝任何形式的“破位”！ 
        # 只要现价低于 MA20 一丁点都不行。咱们只买踩在蹦床上的，不买掉进水里的。 
        if price < ma20: 
            reject_reason = "破位差生：现价跌破MA20生命线，支撑已失效" 
            is_rejected = True 

        # 2. 【新增：斜率硬指标】拒绝均线走平或低头！ 
        # MA20 必须保持昂首向上的姿态，代表过去 20 天的平均成本在持续抬升。 
        elif ma20 <= ma20_yesterday: 
            reject_reason = "趋势走弱：MA20斜率已走平或向下，生命线不再坚挺" 
            is_rejected = True 

        # 3. 【新增：日内深度过滤】拒绝日内跌幅过深的“诱多反抽”！ 
        # 就像招商轮船，虽然收盘回去了，但日内砸太深说明盘面太乱。 
        # 规定：日内最低价跌破 MA20 的幅度不能超过 2%。 
        elif today_low < ma20 * 0.98: 
            reject_reason = "日内重伤：盘中砸盘过深，结构已遭破坏，反抽不可信" 
            is_rejected = True 

        # 4. 【原逻辑保留】战略级底色核查 
        elif price < max_high_120 * 0.80: 
            reject_reason = "超跌反弹：距高点跌幅超20%，套牢盘太重" 
            is_rejected = True 
            
        # 10. 【V4.1新增：均线死结过滤】专杀【英科再生】这种薛定谔的猫！ 
        # 如果 5/10/20/30 四根均线最高值和最低值相差不到 3%，说明彻底拧成了麻花，方向未明。 
        elif (max([ma5, ma10, ma20, ma30]) - min([ma5, ma10, ma20, ma30])) / min([ma5, ma10, ma20, ma30]) < 0.03: 
            reject_reason = "均线死结：5/10/20/30高度粘合，主力装死中，拒绝浪费时间" 
            is_rejected = True 
 
        # 11. 【V4.1新增：短线断头铡刀过滤】专杀【嘉元科技】这种半空飞刀！ 
        # 强势回踩绝不允许 MA5 直接死叉跌穿 MA20。如果 5日线比 20日线还低，说明短期已经发生雪崩。 
        elif ma5 < ma20: 
            reject_reason = "短线破位：MA5已砸穿MA20，短期空头趋势确立，切勿接刀" 
            is_rejected = True 
 
        # 12. 【V4.1新增：头顶泰山压顶过滤】专杀【众源新材】这种被死死压制的票！ 
        # 如果股价不仅低于 MA5，还低于 MA10，并且 MA5 < MA10（短线死叉向下），这叫标准空头压制。 
        elif price < ma5 and price < ma10 and ma5 < ma10: 
            reject_reason = "泰山压顶：现价被MA5和MA10双重死叉压制，反弹阻力极大" 
            is_rejected = True 

        # 13. 【V4.2新增：高空坠物/断头铡刀过滤】专杀【嘉元科技】这种突然暴跌的飞刀！ 
        # 应对均线滞后性：不需要等 MA5 死叉 MA10。只要现价被 MA5 远远抛在头顶（比如现价低于 MA5 超过 4%） 
        # 说明是极其猛烈的短期跳水，此时的 MA20 就像纸糊的蹦床，绝对不能接！ 
        elif (ma5 - price) / ma5 > 0.04: 
            reject_reason = f"高空坠物：现价极速跌落，低于MA5达 {((ma5-price)/ma5*100):.1f}%，不要等死叉，绝对不接飞刀！" 
            is_rejected = True 
 
        # 14. 【V4.2新增：双重击穿防线过滤】 
        # 只要现价一天之内（或短期）同时大幅跌穿了 MA5 和 MA10（距离 MA10 超过 2%），说明上方套牢盘瞬间形成，抛压极大。 
        elif price < ma5 and price < ma10 and (ma10 - price) / ma10 > 0.02: 
            reject_reason = "双线击穿：现价已大幅跌穿5日和10日防线，短线多头结构彻底崩塌！" 
            is_rejected = True 

        # 5. 【原逻辑保留】量能极致萎缩 
        elif vol_ratio > 0.85: 
            reject_reason = f"洗盘不彻底：量比{vol_ratio:.2f}未见极致萎缩" 
            is_rejected = True 
            
        # 6. 【长线牛股基因】MA60 必须在 MA120 上方！ 
        elif ma60 <= ma120: 
            reject_reason = "长线趋势依然向下 (MA60死叉MA120)，只做顺势" 
            is_rejected = True 
 
        # 7. 波段趋势过滤：MA20 必须在 MA60 上方 
        elif ma20 <= ma60: 
            reject_reason = "波段趋势未走好 (MA20在MA60下方)" 
            is_rejected = True 
            
        # 8. 情绪过滤：拒绝接暴跌的飞刀，拒绝追高 
        elif change_percent < -5.0: 
            reject_reason = f"跌幅过大 ({change_percent:.2f}%)，切勿空手接飞刀" 
            is_rejected = True 
        elif change_percent > 4.0: 
            reject_reason = f"拉升中 ({change_percent:.2f}%)，脱离伏击点" 
            is_rejected = True 
            
        # 9. 精准打击区：因为已经限制了price >= ma20，所以只需要限制偏离度不超过 3%
        elif bias_20 > 3.0: 
            reject_reason = f"悬在半空 (乖离率+{bias_20:.2f}%)，极易被埋" 
            is_rejected = True 
 
        return { 
            "code": code, 
            "name": name, 
            "price": price, 
            "change_percent": change_percent, 
            "ma20": ma20, 
            "bias_20": bias_20, 
            "vol_ratio": vol_ratio, 
            "is_rejected": is_rejected, 
            "reject_reason": reject_reason 
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor: 
        futures = {executor.submit(analyze_stock_pullback, code): code for code in codes} 
        for future in concurrent.futures.as_completed(futures): 
            res = future.result() 
            if "error" not in res: 
                results.append(res) 
                
    return jsonify({"status": "success", "results": results}) 
 
@app.route('/api/scan_hot', methods=['POST']) 
def scan_hot(): 
    try: 
        data = request.json or {} 
        exclude_codes = data.get('exclude_codes', []) 
        
        all_hot_codes = [] 
        for page in range(1, 39): 
            try:
                url = f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={page}&num=100&sort=amount&asc=0&node=hs_a" 
                resp = requests.get(url, timeout=10) 
                # 检查响应内容是否为空或非 JSON 格式
                if not resp.text.strip():
                    break
                
                hot_stocks_raw = resp.json() 
                if not hot_stocks_raw: 
                    break 
                
                # 如果返回的是错误信息的字典格式 {"__ERROR": 2, "__ERRORMSG": "Input error"}，跳出循环
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
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor: 
            futures = {executor.submit(analyze_stock_pullback, code): code for code in all_hot_codes} 
            for future in concurrent.futures.as_completed(futures): 
                res = future.result() 
                if "error" not in res and not res.get('is_rejected'): 
                    passed_results.append(res) 
        
        # 优中选优：对于回踩系统，我们优先展示乖离率最接近 0 的（踩得最准的） 
        passed_results.sort(key=lambda x: abs(x['bias_20'])) 
        final_list = passed_results[:20] 
 
        return jsonify({"status": "success", "results": final_list}) 
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)}) 
 
if __name__ == '__main__': 
    app.run(host='0.0.0.0', port=5001, debug=True)