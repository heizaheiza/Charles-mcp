# Tool Contract

閺堫剚鏋冨锝呯暰娑斿缍嬮崜?Charles MCP 瀹搞儱鍙块棃銏犳倻 agent 閻ㄥ嫭甯归懡鎰殶閻劌顨栫痪锔肩礉闁插秶鍋ｇ憰鍡欐磰閿?
- live/history 娑撴槒鐭惧?- summary-first 鐠嬪啰鏁ら弬鐟扮础
- `stop_failed + recoverable=true` 閻ㄥ嫭浠径宥堫嚔娑?- 姒涙顓?token 閹貉冨煑娑撳酣顣╂潻鍥ㄦ姢缁涙牜鏆?
## 1. 閹缍嬮崢鐔峰灟

1. 閸忓牆鍨庣紒鍕剁礉閸?summary閿涘苯鍟€ detail
2. 姒涙顓绘担璺ㄦ暏 `preset="api_focus"`
3. 姒涙顓婚幎?summary 鐟欏棔璐熸稉缁樻殶閹诡喗绨?4. detail 閸欘亜婀?drill-down 閺冭埖澧犳担璺ㄦ暏
5. `stop_live_capture` 閸欘亝婀侀崷?`status="stopped"` 閺冭埖澧犵憴鍡曡礋閻喐顒滈崗鎶芥４ capture

## 2. 瀹搞儱鍙块崚鍡欑矋

### Live capture tools
- `start_live_capture`
- `read_live_capture`
- `peek_live_capture`
- `stop_live_capture`
- `query_live_capture_entries`
- `get_capture_analysis_stats`
- `group_capture_analysis`

### History tools
- `analyze_recorded_traffic`
- `query_recorded_traffic`
- `list_recordings`
- `get_recording_snapshot`
- `get_traffic_entry_detail`

### Status / control tools
- `charles_status`
- `throttling`
- `reset_environment`

### Deprecated tools
- `proxy_by_time`
- `filter_func`

鐠囧瓨妲戦敍?- legacy tools 娴犲懍绻氶悾娆忓悑鐎圭櫢绱濇稉宥呯安閸愬秳缍旀稉鐑樻煀閻ㄥ嫬鍨庨弸鎰瘜閸忋儱褰涢妴?
## 3. 閹恒劏宕橀惃?live 鐠嬪啰鏁ゆい鍝勭碍

1. `start_live_capture`
2. `group_capture_analysis`
3. `query_live_capture_entries`
4. `get_traffic_entry_detail`
5. `stop_live_capture`

娑撹桨绮堟稊鍫ｇ箹娑斿牆浠涢敍?- `group_capture_analysis` 閺堚偓閻?token閿涘矂鈧倸鎮庨崗鍫ｇ槕閸掝偆鍎归悙?host/path/status
- `query_live_capture_entries` 鏉╂柨娲栫紒鎾寸€崠?summary閿涘矂鈧倸鎮?agent 閹镐胶鐢荤粵娑⑩偓?- `get_traffic_entry_detail` 閸欘亜婀涵顔款吇閻╊喗鐖ｉ弶锛勬窗閸氬骸鍟€鐏炴洖绱戠€瑰本鏆ｇ紒鍡氬Ν

## 4. 閹恒劏宕橀惃?history 鐠嬪啰鏁ゆい鍝勭碍

1. `list_recordings`
2. `analyze_recorded_traffic`
3. `group_capture_analysis(source="history")`
4. `get_traffic_entry_detail`

## 5. summary-first 婵傛垹瀹?
### `query_live_capture_entries`

闁倻鏁ら敍?- 瑜版挸澧?live capture 閻ㄥ嫮绮ㄩ弸鍕閸掑棙鐎?
鏉╂柨娲栭柌宥囧仯閿?- `items`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `next_cursor`
- `warnings`

### `analyze_recorded_traffic`

闁倻鏁ら敍?- 閸樺棗褰?`.chlsj` 韫囶偆鍙庨惃鍕波閺嬪嫬瀵查崚鍡樼€?
鏉╂柨娲栭柌宥囧仯閿?- `items`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `warnings`

### `group_capture_analysis`

闁倻鏁ら敍?- 娴?token 閼辨艾鎮庨崚鍡樼€?
閺€顖涘瘮閸掑棛绮嶇€涙顔岄敍?- `host`
- `path`
- `response_status`
- `resource_class`
- `method`
- `host_path`
- `host_status`

鏉╂柨娲栭柌宥囧仯閿?- `groups`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `warnings`

## 6. token 娴兼ê瀵叉總鎴犲

閸掑棙鐎界猾?tools 姒涙顓绘导姘喘閸忓牐绻冨銈忕窗
- `control.charles`
- `CONNECT`
- `static_asset`
- `media`
- `font`
- 閸忔湹绮妯烘珨闂婂厖缍嗘禒宄扳偓鑹邦嚞濮?
姒涙顓婚幒銊ㄥ礃閿?- `preset="api_focus"`
- 娣囨繃瀵旀潏鍐ㄧ毈閻?`max_items`
- 娑撳秷顩︽妯款吇鐠囬攱鐪?full body
- 閸忓牏婀?`group_capture_analysis`
- 閸愬秶婀?`query_live_capture_entries`

婵″倹鐏夌紒鎾寸亯鐞氼偉顥嗛崜顏庣礉agent 鎼存梻绮ㄩ崥鍫窗
- `truncated`
- `filtered_out_count`
- `filtered_out_by_class`

## 7. `stop_live_capture` 婵傛垹瀹?
### 閹存劕濮涢幀?
```json
{
  "status": "stopped",
  "recoverable": false,
  "active_capture_preserved": false
}
```

閸氼偂绠熼敍?- Charles stop 閹存劕濮?- active capture 瀹歌弓绮?server 閻樿埖鈧椒鑵戝〒鍛倞
- 鐠?capture 閸欘垯浜掔憴鍡曡礋閸忔娊妫?
### 閸欘垱浠径宥呫亼鐠愩儲鈧?
```json
{
  "status": "stop_failed",
  "recoverable": true,
  "active_capture_preserved": true
}
```

閸氼偂绠熼敍?- stop 閸︺劋绔村▎锛勭叚闁插秷鐦崥搴濈矝婢惰精瑙?- 鏉╂瑤绗夐弰顖椻偓婊€绱扮拠婵嗗嚒缂佸繒绮ㄩ弶鐔测偓婵堟畱閸氬奔绠熺拠?- active capture 娴犲秳绻氶悾?- 娑斿鎮楁禒宥呭讲閿?  - `read_live_capture`
  - `peek_live_capture`
  - 閸愬秵顐肩拫鍐暏 `stop_live_capture`

### agent 閸?`stop_failed` 閺冭泛绻€妞ゅ浼掔€瑰牏娈戠憴鍕灟

1. 娣囨繄鏆€ `capture_id`
2. 娑撳秷顩﹂崑鍥啎瑜版挸澧?capture 瀹告彃鍙ч梻?3. 鐠囪褰?`error` 鐎涙顔岄幒鎺撶叀婢惰精瑙﹂崢鐔锋礈
4. 濡偓閺?`warnings`
5. 婵″倹婀佽箛鍛邦洣閿涘矁鐨熼悽?`charles_status`
6. 婵″倽绻曢棁鈧拠璇插絿閺佺増宓侀敍宀€鎴风紒?`read_live_capture`
7. 闂団偓鐟曚焦鏁圭亸鐐閿涘矂鍣哥拠?`stop_live_capture`
8. 閸欘亝婀侀崷?`status="stopped"` 閺冭绱濋幍宥堫潒娑撳搫鍙ч梻顓炵暚閹?
### warning 鐠囶厺绠?
- `stop_recording_retry_succeeded`
  - 缁楊兛绔村▎?stop 婢惰精瑙﹂敍宀€鐓柌宥堢槸閸氬孩鍨氶崝?- `stop_recording_failed_after_retry`
  - 娑撱倖顐?stop 闁棄銇戠拹銉礉鏉╂稑鍙嗛崣顖涗划婢跺秴銇戠拹銉︹偓?
## 8. 鐎瑰鍙忔稉搴ゅ姎閺佸繐顨栫痪?
姒涙顓绘惔鏃囶潒娑撻缚鍔氶弫蹇氱翻閸戞亽鈧?
姒涙顓婚懘杈ㄦ櫛鐎涙顔岄崠鍛娴ｅ棔绗夐梽鎰艾閿?- `Authorization`
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

鐠囧瓨妲戦敍?- summary 鏉堟挸鍤惔鏂款潗缂佸牐顫嬫稉楦垮姎閺佸繗顫嬮崶?- detail 姒涙顓绘稊鐔风安閺勵垵鍔氶弫蹇氼潒閸?- 閸欘亝婀侀弰搴ｂ€橀棁鈧憰浣规閹靛秴绨茬拠閿嬬湴閺囨潙鐣弫瀵告畱 detail

## 9. detail drill-down 婵傛垹瀹?
### `get_traffic_entry_detail`

閹恒劏宕橀悽銊┾偓鏃撶窗
- 鐎电懓宕熼弶?entry 閸嬫氨绨跨紒鍡楀瀻閺?- 娑撳秶鏁ゆ禍搴㈠闁插繑濯洪崗銊╁櫤 body

閹恒劏宕樼憴鍕灟閿?1. 閸忓牓鈧俺绻?summary 閹?group 绾喖鐣?`entry_id`
2. 閸愬秷鐨熼悽?`get_traffic_entry_detail`
3. 濞屸剝婀侀弰搴ｂ€樿箛鍛邦洣閺冭绱濇稉宥堫洣姒涙顓?`include_full_body=true`
4. 濞屸剝婀侀弰搴ｂ€樿箛鍛邦洣閺冭绱濇稉宥堫洣姒涙顓?`include_sensitive=true`

## 10. 闁板秶鐤嗘稉搴″弳閸?
閹恒劏宕橀崗銉ュ經閿?- `charles-mcp`
- `python -c "from charles_mcp.main import main; main()"`

閺嶇绺鹃悳顖氼暔閸欐﹢鍣洪敍?- `CHARLES_USER`
- `CHARLES_PASS`
- `CHARLES_PROXY_HOST`
- `CHARLES_PROXY_PORT`
- `CHARLES_MANAGE_LIFECYCLE`

閹恒劏宕樻妯款吇閿?- `CHARLES_MANAGE_LIFECYCLE=false`

閸樼喎娲滈敍?- MCP server 姒涙顓绘稉宥呯安閸︺劑鈧偓閸戠儤妞傞弴璺ㄦ暏閹村嘲鍙ч梻?Charles 鏉╂稓鈻?
## 11. 缂佸牏顏稉搴☆吂閹撮顏柊宥囩枂瀵ら缚顔?
### PowerShell

```powershell
$env:CHARLES_USER = "admin"
$env:CHARLES_PASS = "123456"
$env:CHARLES_MANAGE_LIFECYCLE = "false"
charles-mcp
```

### Windows CMD

```cmd
set CHARLES_USER=admin
set CHARLES_PASS=123456
set CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### Bash / Zsh / Git Bash

```bash
export CHARLES_USER=admin
export CHARLES_PASS=123456
export CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### 闁氨鏁?MCP stdio 闁板秶鐤?
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

### Codex CLI

```toml
[mcp_servers.charles]
command = "charles-mcp"

[mcp_servers.charles.env]
CHARLES_USER = "admin"
CHARLES_PASS = "123456"
CHARLES_MANAGE_LIFECYCLE = "false"
```

### Antigravity

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