# Charles MCP Server

[English README](README.en.md) | [Tool Contract](docs/contracts/tools.md)

Charles Proxy 閻?MCP 闂嗗棙鍨氬銉ュ徔閿涘矂娼伴崥?agent 閻ㄥ嫭鐗宠箛鍐厴閸旀稑瀵橀幏顒婄窗

- 鐠囪褰?Charles 瑜版挸澧?session 閻ㄥ嫬鐤勯弮璺侯杻闁插繑鏆熼幑顕嗙礉閼板奔绗夐弰顖濐嚖鐠囪宸婚崣?`.chlsj`
- 鐎?live/history 娑撱倖娼弫鐗堝祦闁俺鐭鹃崑姘辩埠娑撯偓閸掑棙鐎?- 姒涙顓绘导妯哄帥缁涙稑鍤崗鎶芥暛 API 鐠囬攱鐪伴敍宀冪箖濠娿倕娴橀悧鍥モ偓浣哥摟娴ｆ挶鈧礁鐛熸担鎾剁搼妤傛ê娅旈棅瀹犵カ濠?- 姒涙顓婚懘杈ㄦ櫛閿涘矂浼╅崗宥嗗Ω `Authorization`閵嗕梗Cookie`閵嗕辜oken 缁涘鏅遍幇鐔告殶閹诡喚娲块幒銉︽瘹闂囪尙绮?agent
- 姒涙顓?summary-first閿涘本甯堕崚?token 濞戝牐鈧绱漝etail drill-down 閺冭泛鍟€鐏炴洖绱戠€瑰本鏆ｉ崘鍛啇

## 瀹搞儱鍙挎禍顔惧仯

1. 鐎圭偞妞傞幎鎾冲瘶閸欘垵顕?- `start_live_capture` / `read_live_capture` / `peek_live_capture` / `stop_live_capture`
- 閺€顖涘瘮鏉堢懓缍嶆潏鍦箙鏉堢懓鍨庨弸鎰剁礉娑撳秹娓剁憰浣虹搼瑜版洖鍩楃紒鎾存将

2. token 閸欏銈介惃鍕瀻閺嬫劘绶崙?- `query_live_capture_entries`
- `analyze_recorded_traffic`
- `group_capture_analysis`
- 姒涙顓?`preset="api_focus"`閿涘奔绱崗鍫ｇ箲閸?API/JSON 鐠囬攱鐪?- 姒涙顓荤紒鐔活吀楠炴儼绻冨?`static_asset`閵嗕梗media`閵嗕梗font`閵嗕梗connect_tunnel` 缁涘鐝崳顏堢叾鐠у嫭绨?
3. 缂佹挻鐎崠?detail drill-down
- `get_traffic_entry_detail`
- 姒涙顓绘潻鏂挎礀閼磋鲸鏅遍崥搴ｆ畱 detail
- 閸欘亝婀侀弰鎯х础鐠囬攱鐪伴弮鑸靛鐏炴洖绱戦弴鏉戠暚閺佸娈?request/response 缂佸棜濡?
4. 閺囧菙閻?stop 閺€璺虹啲
- `stop_live_capture` 閸愬懘鍎存导姘粵娑撯偓濞嗭紕鐓柌宥堢槸
- 閼汇儰琚卞▎?stop 闁棄銇戠拹銉礉鏉╂柨娲?`status="stop_failed"`
- 閸氬本妞傛潻鏂挎礀 `recoverable=true` 娑?`active_capture_preserved=true`
- 鏉╂瑨銆冪粈?active capture 娴犲秳绻氶悾娆欑礉agent 閸欘垯浜掔紒褏鐢荤拠璇插絿閹存牕鍟€濞?stop閿涘矁鈧奔绗夐弰顖滄纯閹恒儰娑悩鑸碘偓?
## 瑜版挸澧犻懗钘夊濮掑倽顫?
瑜版挸澧?server 閺嗘挳婀舵稉澶岀矋娑撴槒顩﹂懗钘夊閿?
1. Live capture tools
- `start_live_capture`
- `read_live_capture`
- `peek_live_capture`
- `stop_live_capture`
- `query_live_capture_entries`
- `get_capture_analysis_stats`
- `group_capture_analysis`

2. History tools
- `analyze_recorded_traffic`
- `query_recorded_traffic`
- `list_recordings`
- `get_recording_snapshot`
- `get_traffic_entry_detail`

3. Status / control tools
- `charles_status`
- `throttling`
- `reset_environment`

閸忕厧顔愭穱婵堟殌娴ｅ棔绗夊楦款唴缂佈呯敾閻劋绨稉鏄忕熅瀵板嫮娈?legacy tools閿?
- `proxy_by_time`
- `filter_func`

## 鏉╂劘顢戠憰浣圭湴

- Python 3.10+
- 閺堫剚婧€瀹告彃鎯庨崝?Charles Proxy
- Charles Web Interface 瀹告彃鎯庨悽?- Charles 娴狅絿鎮婃妯款吇閻╂垵鎯?`127.0.0.1:8888`

## 鐎瑰顥?
瀵偓閸欐垹骞嗘晶鍐跨窗

```bash
pip install -e .[dev]
```

鐎瑰顥婇崥搴ｆ畱閸涙垝鎶ら崗銉ュ經閿?
```bash
charles-mcp
```

閸栧懎鍙嗛崣锝忕窗

```text
charles_mcp.main:main
```

娴犳挸绨遍崘鍛悑鐎圭懓鍙嗛崣锝忕窗

```bash
python charles-mcp-server.py
```

## 閻滎垰顣ㄩ崣姗€鍣?
| 閸欐﹢鍣?| 姒涙顓婚崐?| 鐠囧瓨妲?|
| --- | --- | --- |
| `CHARLES_USER` | `admin` | Charles Web Interface 閻劍鍩涢崥?|
| `CHARLES_PASS` | `123456` | Charles Web Interface 鐎靛棛鐖?|
| `CHARLES_PROXY_HOST` | `127.0.0.1` | Charles 娴狅絿鎮婃稉缁樻簚 |
| `CHARLES_PROXY_PORT` | `8888` | Charles 娴狅絿鎮婄粩顖氬經 |
| `CHARLES_CONFIG_PATH` | 閼奉亜濮╅幒銏＄ゴ | Charles 闁板秶鐤嗛弬鍥︽鐠侯垰绶?|
| `CHARLES_REQUEST_TIMEOUT` | `10` | 閹貉冨煑闂?HTTP 鐡掑懏妞傜粔鎺撴殶 |
| `CHARLES_MAX_STOPTIME` | `3600` | 缁傝崵鍤庤ぐ鏇炲煑閺堚偓婢堆勬闂€?|
| `CHARLES_MANAGE_LIFECYCLE` | `false` | 閺勵垰鎯侀悽?MCP server 閸︺劌鎯庨崝?闁偓閸戠儤妞傜粻锛勬倞 Charles 閻㈢喎鎳￠崨銊︽埂 |

`CHARLES_MANAGE_LIFECYCLE=false` 閺勵垶绮拋銈嗗腹閼芥劕鈧鈧倿绮拋銈嗗剰閸愬吀绗呴敍瀛P server 娑撳秴绨查崷銊┾偓鈧崙鐑樻閺囪法鏁ら幋宄板彠闂?Charles 鏉╂稓鈻奸妴?
## 閸氬嫮顫掔紒鍫㈩伂娑擃厾娈戦柊宥囩枂閺傝纭?
### PowerShell

瑜版挸澧犳导姘崇樈閿?
```powershell
$env:CHARLES_USER = "admin"
$env:CHARLES_PASS = "123456"
$env:CHARLES_PROXY_HOST = "127.0.0.1"
$env:CHARLES_PROXY_PORT = "8888"
$env:CHARLES_MANAGE_LIFECYCLE = "false"
charles-mcp
```

### Windows CMD

```cmd
set CHARLES_USER=admin
set CHARLES_PASS=123456
set CHARLES_PROXY_HOST=127.0.0.1
set CHARLES_PROXY_PORT=8888
set CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### Git Bash / Bash / Zsh

```bash
export CHARLES_USER=admin
export CHARLES_PASS=123456
export CHARLES_PROXY_HOST=127.0.0.1
export CHARLES_PROXY_PORT=8888
export CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### 閻╁瓨甯撮悽?Python 閸忋儱褰涢崥顖氬З

闁倸鎮庢稉宥嗗厒娓氭繆绂?console script閿涘本鍨ㄩ懓鍛存付鐟曚礁婀禒缁樺壈缂佸牏顏柌灞炬▔瀵繑瀵氱€规艾鍙嗛崣锝忕窗

```bash
python -c "from charles_mcp.main import main; main()"
```

## 閸氬嫮琚?MCP 鐎广垺鍩涚粩顖欒厬閻ㄥ嫰鍘ょ純顔芥煙濞?
### 闁氨鏁?stdio MCP 闁板秶鐤?
闁倻鏁ゆ禍搴㈡暜閹?`command + args + env` 閻?MCP 鐎广垺鍩涚粩顖樷偓?
```json
{
  "mcpServers": {
    "charles": {
      "command": "charles-mcp",
      "env": {
        "CHARLES_USER": "admin",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```

### Claude Desktop 妞嬪孩鐗搁柊宥囩枂

婵″倹鐏夌€广垺鍩涚粩顖氬帒鐠佸憡妯夊蹇斿瘹鐎?Python 閸忋儱褰涢敍灞藉讲娴犮儴绻栭弽宄板晸閿?
```json
{
  "mcpServers": {
    "charles": {
      "command": "python",
      "args": ["-c", "from charles_mcp.main import main; main()"],
      "env": {
        "CHARLES_USER": "admin",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```

### 娴犳挸绨遍張顒€婀村鈧崣鎴﹀帳缂?
闁倸鎮庨惄瀛樺复閸︺劋绮ㄦ惔鎾诲櫡鏉╂劘顢戦敍?
```json
{
  "mcpServers": {
    "charles": {
      "command": "python",
      "args": ["charles-mcp-server.py"],
      "cwd": "E:/project/Charles-mcp",
      "env": {
        "CHARLES_USER": "admin",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```

## 閹恒劏宕樻担璺ㄦ暏閺傜懓绱?
### 鐎圭偞妞傞崚鍡樼€芥稉鏄忕熅瀵?
閹恒劏宕樼紒?agent 閻ㄥ嫯鐨熼悽銊┿€庢惔蹇ョ窗

1. `start_live_capture`
2. `group_capture_analysis`
3. `query_live_capture_entries`
4. `get_traffic_entry_detail`
5. `stop_live_capture`

閸樼喎娲滈敍?- `group_capture_analysis` 閸忓牏绮伴悜顓犲仯閸掑棛绮嶉敍灞炬付閻?token
- `query_live_capture_entries` 閸愬秵瀣佺紒鎾寸€崠?summary
- `get_traffic_entry_detail` 閸欘亜婀涵顔款吇閺屾劖娼拠閿嬬湴閸婄厧绶遍惇瀣閸愬秴鐫嶅鈧?
### 閸樺棗褰堕崚鍡樼€芥稉鏄忕熅瀵?
閹恒劏宕樻い鍝勭碍閿?
1. `list_recordings`
2. `analyze_recorded_traffic`
3. `group_capture_analysis(source="history")`
4. `get_traffic_entry_detail`

## Agent 鐠嬪啰鏁ょ憴鍕瘱

### 1. 姒涙顓婚崗鍫ｈ泲閸掑棛绮嶉敍灞藉晙鐠?summary閿涘苯鍟€ drill-down

娑撳秵甯归懡鎰瀵偓婵姘ㄩ惄瀛樺复閹峰銇囬幍褰掑櫤 detail閵嗗倹甯归懡鎰般€庢惔蹇ョ窗

1. `group_capture_analysis`
2. `query_live_capture_entries` 閹?`analyze_recorded_traffic`
3. `get_traffic_entry_detail`

### 2. 姒涙顓绘担璺ㄦ暏 `preset="api_focus"`

鏉╂瑤閲?preset 娴兼矮绱崗鍫滅箽閻ｆ瑱绱?- JSON / API / GraphQL / Auth 鐠囬攱鐪?- 妤傛ü绱崗鍫㈤獓閻ㄥ嫬褰夐弴鏉戠€烽弬瑙勭《閿涙瓪POST`閵嗕梗PUT`閵嗕梗PATCH`閵嗕梗DELETE`
- 闁挎瑨顕ょ拠閿嬬湴

楠炲爼绮拋銈堢箖濠娿倖鍨ㄩ梽宥嗘綀閿?- `control.charles`
- `CONNECT`
- 閸ュ墽澧?- 鐎涙ぞ缍?- 婵帊缍?- 婢堆囧櫤闂堟瑦鈧浇绁┃?
### 3. 姒涙顓婚幎?summary 瑜版挷缍旀稉缁樻殶閹诡喗绨?
summary 鏉╂柨娲栭惃鍕Ц agent 閸欏銈介惃鍕秵 token 鐟欏棗娴橀敍灞藉瘶閸氼偓绱?- method / host / path / status
- content-type
- 閸忔娊鏁?header 閹芥顩?- request/response body preview
- `matched_fields`
- `match_reasons`
- `redactions_applied`
- `filtered_out_by_class`

### 4. 閸欘亝婀侀弰搴ｂ€橀棁鈧憰浣规閸愬秶婀?detail

閸欘亝婀佽ぐ鎾寸厙閺?entry 瀹歌尙绮＄悮顐も€樼拋銈呪偓鐓庣繁濞ｈ鲸瀵查弮璁圭礉閹靛秷鐨熼悽顭掔窗
- `get_traffic_entry_detail`

婵″倹鐏夊▽鈩冩箒閺勫海鈥橀棁鈧憰渚婄礉娑撳秷顩︽妯款吇閹?`include_full_body=true`閵?
## `stop_failed + recoverable=true` 閻ㄥ嫬顦╅悶鍡氼潐閼?
`stop_live_capture` 閻滄澘婀張澶夎⒈缁夊秶菙鐎规氨濮搁幀渚婄窗

1. `status="stopped"`
- 鐠囧瓨妲?stop 閹存劕濮?- active capture 瀹稿弶绔婚悶?- 婵″倹鐏?`persist=true`閿涘苯褰查懗鍊熺箲閸?`persisted_path`

2. `status="stop_failed"`
- 鐠囧瓨妲?stop 閸︺劋绔村▎锛勭叚闁插秷鐦崥搴濈矝婢惰精瑙?- 鏉╂瑤绗夐弰顖椻偓婊€绱扮拠婵嗗嚒缂佸繒绮ㄩ弶鐔测偓婵堟畱閸氬奔绠熺拠?- 韫囧懘銆忕紒鎾虫値娑撳娼版稉銈勯嚋鐎涙顔岀憴锝夊櫞閿?  - `recoverable=true`
  - `active_capture_preserved=true`

### agent 韫囧懘銆忔俊鍌欑秿婢跺嫮鎮?`stop_failed`

瑜版捁绻戦崶鐑囩窗

```json
{
  "status": "stop_failed",
  "recoverable": true,
  "active_capture_preserved": true
}
```

agent 閻ㄥ嫭顒滅涵顔碱槱閻炲棙鏌熷蹇旀Ц閿?
1. 娑撳秷顩︽稉銏犵磾 `capture_id`
2. 娑撳秷顩﹂崑鍥啎 Charles 瀹歌尙绮￠崑婊勵剾瑜版洖鍩?3. 鐠囪褰?`error` 娑?`warnings`
4. 婵″倿娓剁涵顔款吇瑜版挸澧犻悩鑸碘偓渚婄礉閸忓牐鐨熼悽?`charles_status`
5. 婵″倿娓剁涵顔款吇閺佺増宓侀弰顖氭儊娴犲秴褰茬拠浼欑礉閸欘垳鎴风紒顓＄殶閻?`read_live_capture`
6. 婵″倿娓剁紒褏鐢婚弨璺虹啲閿涘苯绨查崘宥嗩偧鐠嬪啰鏁?`stop_live_capture`
7. 閸欘亝婀侀崷?`status="stopped"` 閺冭绱濋幍宥嗗Ω鐠?capture 鐟欏棔璐熼惇鐔割劀閸忔娊妫?
### `stop_live_capture` 閻ㄥ嫭浠径宥堫嚔娑?
- 閸愬懘鍎存导姘粵娑撯偓濞嗭紕鐓柌宥堢槸
- 婵″倹鐏夌粭顑跨癌濞嗏剝鍨氶崝鐕傜窗
  - 鏉╂柨娲?`status="stopped"`
  - `warnings` 闁插苯褰查懗钘夊瘶閸?`stop_recording_retry_succeeded`
- 婵″倹鐏夋稉銈嗩偧闁棄銇戠拹銉窗
  - 鏉╂柨娲?`status="stop_failed"`
  - `recoverable=true`
  - `active_capture_preserved=true`
  - `warnings` 闁插苯瀵橀崥?`stop_recording_failed_after_retry`

鏉╂瑦娼總鎴犲閻ㄥ嫮娲伴惃鍕剁礉閺勵垵顔€ agent 閼宠棄婀幒褍鍩楅棃銏㈢仜閺冭泛銇戠拹銉︽缂佈呯敾閹垹顦查敍宀冣偓灞肩瑝閺勵垳娲块幒銉﹀Ω live capture 閻樿埖鈧椒娑幒澶堚偓?
## 娑撴槒顩﹀銉ュ徔鐠囧瓨妲?
### `start_live_capture`

閻劑鈧棑绱?- 閸氼垰濮╂稉鈧稉顏呮煀閻?live capture
- 閹存牗甯寸粻鈥崇秼閸撳秴鍑￠崷銊ョ秿閸掑墎娈?Charles session

鐢摜鏁ら崣鍌涙殶閿?- `reset_session`
- `include_existing`
- `adopt_existing`

### `read_live_capture`

閻劑鈧棑绱?- 鐠囪褰囪ぐ鎾冲 live capture 閻ㄥ嫬顤冮柌蹇旀殶閹?
鏉╂柨娲栭崗鎶芥暛鐎涙顔岄敍?- `capture_id`
- `status`
- `items`
- `next_cursor`
- `total_new_items`
- `truncated`
- `warnings`

### `query_live_capture_entries`

閻劑鈧棑绱?- 鐎?live capture 閸嬫氨绮ㄩ弸鍕閸掑棙鐎介弻銉嚄
- 姒涙顓婚弴鎾偓鍌氭値 agent 濞戝牐鍨?
閺€顖涘瘮闁插秶鍋ｉ崣鍌涙殶閿?- `preset`
- `method_in`
- `status_in`
- `resource_class_in`
- `request_content_type`
- `response_content_type`
- `request_json_query`
- `response_json_query`

### `group_capture_analysis`

閻劑鈧棑绱?- 鐎?live 閹?history 閺佺増宓侀崑姘秵 token 閼辨艾鎮庨崚鍡樼€?- 闁倸鎮庨崗鍫㈡箙閻戭厾鍋?host/path/status 閸愬秴鍠呯€?drill-down

閺€顖涘瘮閸掑棛绮嶇€涙顔岄敍?- `host`
- `path`
- `response_status`
- `resource_class`
- `method`
- `host_path`
- `host_status`

### `analyze_recorded_traffic`

閻劑鈧棑绱?- 鐎电懓宸婚崣?`.chlsj` 瑜版洖鍩楃紒鎾寸亯閸嬫氨绮ㄩ弸鍕閸掑棙鐎?
### `get_traffic_entry_detail`

閻劑鈧棑绱?- 閺屻儳婀呴崡鏇熸蒋鐠囬攱鐪伴惃?detail
- 姒涙顓绘禒宥囧姧閼磋鲸鏅?
瀵ら缚顔呴敍?- 濞屸剝婀佽箛鍛邦洣閺冩湹绗夌憰渚€绮拋?`include_sensitive=true`
- 濞屸剝婀佽箛鍛邦洣閺冩湹绗夌憰渚€绮拋?`include_full_body=true`

## 鐎瑰鍙忔稉搴ㄧ帛鐠併倛鍔氶弫?
姒涙顓绘导姘冲姎閺佸繒娈戦弫蹇斿妳鐎涙顔岄崠鍛娴ｅ棔绗夐梽鎰艾閿?
- `Authorization`
- `Proxy-Authorization`
- `Cookie`
- `Set-Cookie`
- `X-Api-Key`
- `token`
- `access_token`
- `refresh_token`
- `session`
- `password`
- `secret`

summary 鐟欏棗娴樻慨瀣矒鎼存棁顕氱悮顐ヮ潒娑撻缚鍔氶弫蹇氼潒閸ヤ勘鈧?
## 娑撳秵甯归懡鎰埛缂侇厽澧跨仦鏇犳畱閺冄冧紣閸?
娴犮儰绗呭銉ュ徔娣囨繄鏆€閸忕厧顔愰敍灞肩稻娑撳秴绨茬紒褏鐢绘担婊€璐熸稉鏄忕熅瀵板嫪濞囬悽顭掔窗

- `proxy_by_time`
- `filter_func`

閸樼喎娲滈敍?- 鐎瑰啩婊戞稉宥夆偓鍌氭値娴ｆ粈璐熼弬鎵畱閸掑棙鐎介懗钘夊閸忋儱褰?- 閺傛壆娈?live/history 閸掑棙鐎介懗钘夊瀹歌尙绮￠悽杈╃波閺嬪嫬瀵?tools 閺囧じ鍞?
## 瀵偓閸欐垳绗屾宀冪槈

鏉╂劘顢戝ù瀣槸閿?
```bash
python -m pytest -q
```

鐢摜鏁ら張顒€婀村Λ鈧弻銉窗

```bash
python charles-mcp-server.py
python -c "from charles_mcp.main import main; main()"
```

閺囨潙顦垮銉ュ徔婵傛垹瀹虫稉?agent 鐠嬪啰鏁ょ痪锕€鐣剧憴渚婄窗
- [docs/contracts/tools.md](docs/contracts/tools.md)
- [README.en.md](README.en.md)

## 新增客户端配置补充

### Claude CLI

```bash
claude mcp add-json charles '{
  "type": "stdio",
  "command": "charles-mcp",
  "env": {
    "CHARLES_USER": "admin",
    "CHARLES_PASS": "123456",
    "CHARLES_MANAGE_LIFECYCLE": "false"
  }
}'
```

仓库开发态可改成：

```bash
claude mcp add-json charles '{
  "type": "stdio",
  "command": "python",
  "args": ["E:/project/Charles-mcp/charles-mcp-server.py"],
  "env": {
    "CHARLES_USER": "admin",
    "CHARLES_PASS": "123456",
    "CHARLES_MANAGE_LIFECYCLE": "false"
  }
}'
```

### Codex CLI

`~/.codex/config.toml` 示例：

```toml
[mcp_servers.charles]
command = "charles-mcp"

[mcp_servers.charles.env]
CHARLES_USER = "admin"
CHARLES_PASS = "123456"
CHARLES_MANAGE_LIFECYCLE = "false"
```

仓库开发态可改成：

```toml
[mcp_servers.charles]
command = "python"
args = ["E:/project/Charles-mcp/charles-mcp-server.py"]

[mcp_servers.charles.env]
CHARLES_USER = "admin"
CHARLES_PASS = "123456"
CHARLES_MANAGE_LIFECYCLE = "false"
```

### Antigravity

在 `Manage MCP Servers` 或 `View raw config` 中加入：

```json
{
  "mcpServers": {
    "charles": {
      "command": "charles-mcp",
      "env": {
        "CHARLES_USER": "admin",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```