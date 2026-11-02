# VertiGEO 电商版详细设计文档（MVP）

## 1. 文档信息

- **产品**：VertiGEO 电商版
- **版本**：v1.0，取代 v0.3
- **状态**：已确认，作为实现依据
- **关联**：`VertiGEO-电商版产品说明书.md`、`VertiGEO-电商版开发计划.md`
- **数据库**：PostgreSQL，库 `ck`，schema `geo`。表已创建，本文描述现表，不另起一套字段名

产品说明书里仍有两处旧措辞：付费才含导出，以及付费含深度建议。实现以本文第 3.3 节为准。

## 2. 目标

用户粘贴商品页、分类页或店铺首页 URL。系统抓取公开 HTML，用纯规则给出 0–100 的 GEO 健康分、五个子维度、前 30% 窗口诊断、问题列表，以及可替换的 JSON-LD。后台已配置的模型再生成可复制文案。

评分不调用大模型。用户界面不出现模型供应商、模型名和 API Key。

## 3. 范围

### 3.1 MVP 包含

- 匿名评分，每日次数由 `anonymous_daily_limit` 控制，初始值 3
- 邮箱密码注册。注册用户每日次数由 `registered_daily_limit` 控制，初始值 20
- 注册用户的历史记录，以及 Markdown / PDF 导出
- 五维规则评分，以及规则生成的 Product / Offer / AggregateRating JSON-LD
- 模型生成三项文案：自包含商品描述、FAQ、问题式标题
- 基础会员：微信支付或支付宝购买一个月，生效后取消每日次数限制
- 专业会员：订阅页展示；批量、开放 API、白标返回未开放
- 管理后台：模型、计划、订阅、用量、每日次数
- 桌面与 375px 宽度可用

### 3.2 MVP 不包含

- 无头浏览器。脚本渲染后才出现的正文视为抓取失败或技术可访问性失分
- 第三方登录
- 批量 URL、对外开放 API、白标模板
- 按会员切换不同提示词的「深度建议」
- 对比表生成。产品说明书写过这一项，MVP 模型输出不含对比表
- 物流及其他行业规则
- 二级查询索引。主键、唯一约束、外键保留
- 年付，以及微信委托代扣、支付宝周期扣款。月付是一次付款购买一个自然月

### 3.3 已确认决策

| 事项 | 决定 |
|------|------|
| 导出 | 注册用户即可导出。基础会员只解除每日次数限制 |
| Schema | 只由规则引擎生成和修正。模型不产出 Schema |
| 文案 | 模型只写商品描述、FAQ、问题式标题 |
| 技术栈 | FastAPI + Next.js |
| 专业会员 | 只展示，不实现批量、开放 API、白标 |
| 管理员与次数 | 使用已有 `t_users.role`、`geo.t_settings`。首个管理员邮箱为 `258095357@qq.com` |
| 订阅价格 | 人民币，仅月付。基础会员标价 9.9，专业会员标价 19.9。管理员可改标价和减免金额 |
| 支付渠道 | 微信支付与支付宝。不用 Stripe |

## 4. 角色与权益

| 角色 | 判定 | 评分次数 | 历史 | 导出 | 其他 |
|------|------|----------|------|------|------|
| 匿名 | 无登录会话 | 当日 `anonymous_daily_limit` | 无 | 无 | 达上限时提示注册 |
| 注册用户 | `role=user`，无有效订阅 | 当日 `registered_daily_limit` | 仅自己的记录 | 仅自己的记录 | — |
| 基础会员 | `plan_code=basic` 且订阅有效 | 不限 | 同注册用户 | 同注册用户 | — |
| 专业会员 | `plan_code=pro` 且订阅有效 | 不限 | 同注册用户 | 同注册用户 | 批量、开放 API、白标返回未开放 |
| 管理员 | `role=admin` | 按该账号自身的会员状态 | 同注册用户 | 同注册用户 | 管理接口与后台页面 |

有效订阅：`status=active`，且 `current_period_end` 晚于当前时间。到期前取消只表示本期结束后不再续费，本期仍有效。

注册接口不接受角色参数。邮箱与 `t_settings` 中的 `admin_email` 一致时（忽略大小写），注册成功后 `role=admin`；其余账号为 `user`。当前 `admin_email` 为 `258095357@qq.com`。该邮箱尚未注册，库里还没有对应用户，密码在注册时由本人设置。

## 5. 系统结构

```
浏览器（Next.js）
    │  Cookie 会话，匿名请求带 device_id
    ▼
FastAPI
    ├── 限额
    ├── 抓取与抽取
    ├── 规则评分与 Schema
    ├── 建议生成（读取 t_model_configs）
    ├── 账号、历史、导出
    ├── 订阅与微信 / 支付宝支付通知
    └── 管理接口
    │
    ▼
PostgreSQL  schema geo
```

```
geo/
  apps/api/          FastAPI
  apps/web/          Next.js
  fixtures/pages/    评分夹具 HTML
```

API 连接数据库时设置 `search_path=geo`。不重建已有表。

评分在一次 HTTP 请求内完成，不引入任务队列。时间预算：抓取 15 秒，规则 1 秒，模型 12 秒。前端在等待时显示「抓取 → 分析 → 生成」，响应返回后进入完成态。

### 5.1 一次评分的顺序

1. 校验 URL 形式。
2. 判断登录态与订阅，读取 `t_settings`，统计当日已成功次数。超限则直接返回，不抓取。
3. 抓取 HTML。失败不写 `t_scores`，不扣次数。
4. 抽取字段，计算规则分和 JSON-LD。规则无法得出分数时不写记录，不扣次数。
5. 若存在启用的模型，则生成文案。模型全部失败仍保留分数。
6. 写入 `t_scores`。登录用户写入 `user_id`。同时写入 `t_usage_logs`。
7. 返回分数、诊断、问题、Schema、建议和剩余次数。

## 6. 抓取与抽取

### 6.1 抓取限制

- 只允许 `http` 和 `https`。拒绝缺少主机名、或 URL 中带用户名密码的地址。
- DNS 解析后的每个 IP 都必须是公网地址。拒绝回环、链路本地、私网、云元数据地址（含 `169.254.169.254`）。
- 每次重定向都重新做上述检查。重定向最多 5 次。
- 超时 15 秒。正文上限 2 MB。内容类型必须是 HTML。
- 不执行页面中的脚本。

抓取失败时向用户返回原因类别：地址无效、目标不可达、非公开地址、非 HTML、页面过大、超时。JS 渲染页若可见正文过短，评分仍可返回，技术可访问性按第 8.5 节扣分，并提示「当前无法读取脚本渲染后的正文」。

### 6.2 页面类型

按顺序判断，命中即停止：

| 类型 | 条件 |
|------|------|
| `product` | 存在 Product JSON-LD，或同时出现价格和「加入购物车 / 立即购买」一类操作 |
| `category` | 同一列表中至少 3 个带独立链接的商品名 |
| `store` | 有店铺或品牌名，且有分类入口或商品入口，但达不到 `category` 的列表条件 |
| `unknown` | 以上都不满足 |

`unknown` 仍评分，实体维度按商品页规则扣缺失项。

### 6.3 前 30% 窗口

去掉 `script`、`style`、`noscript` 后取可见文本，压缩连续空白。窗口为该文本的前 30% 字符，至少保留 1 个字符。不用浏览器视口，也不用像素高度。

诊断结果包含：窗口摘录（最多 500 字）、商品名是否在窗口内、价格是否在窗口内、是否有带单位的规格、是否有可独立引用的句子。

可独立引用的句子：窗口内一句长度 20–180 个字符，并且含数字，或含价格、规格、品牌、库存、物流之一。

### 6.4 抽取字段

商品名、品牌、价格、货币、库存、规格（名、值、单位）、评分、评论数、物流文案、标题层级、列表、表格、FAQ 区块、页面内 JSON-LD、可见正文字数、HTTP 状态、是否因 2 MB 上限截断。

价格优先取 Offer JSON-LD，其次取可见文本中带货币符号或货币代码的数字。规格从表格、定义列表和「名称: 值」短行提取。

## 7. 分数如何合成

五个维度各自先得到 0–100 的内部整数分，再合成总分：

```
总分 = round(可引用性 × 0.35 + 实体完整性 × 0.25 + 结构清晰度 × 0.20 + Schema × 0.10 + 技术可访问性 × 0.10)
```

总分限制在 0–100。同一 HTML 重复评分，分数和问题 ID 必须相同。模型失败不影响分数。

每个未满分的检查项生成一条问题：

| 字段 | 含义 |
|------|------|
| `id` | 稳定规则编号，如 `CIT-02` |
| `severity` | `P0` 或 `P1` |
| `dimension` | `citability`、`entity`、`structure`、`schema`、`technical` |
| `message` | 给用户看的一句话 |
| `evidence` | 摘录或选择器；没有内容时说明缺失 |

`P0` 只用于：商品页窗口内缺少商品名、商品页窗口内缺少价格、可见正文为空。其余未满分项为 `P1`。

## 8. 分维度规则

### 8.1 可引用性，权重 35%

商品页和 `unknown`：

| 编号 | 分值 | 满分条件 | 未满分 |
|------|------|----------|--------|
| CIT-01 | 25 | 抽到的商品名出现在前 30% 窗口 | 商品页缺商品名时为 P0 |
| CIT-02 | 25 | 窗口内有价格和货币 | 商品页缺价格时为 P0 |
| CIT-03 | 25 | 窗口内至少一项规格带单位 | P1 |
| CIT-04 | 25 | 窗口内至少一句可独立引用 | P1 |

分类页和店铺首页改为：

| 编号 | 分值 | 满分条件 |
|------|------|----------|
| CIT-11 | 50 | 窗口内至少 1 个商品名 |
| CIT-12 | 50 | 窗口内至少 1 个价格 |

窗口内没有任何商品名记 P0。

### 8.2 实体完整性，权重 25%

商品页和 `unknown`，五项各 20 分：价格 `ENT-01`、规格 `ENT-02`、库存 `ENT-03`、品牌 `ENT-04`、物流 `ENT-05`。字段来自整页抽取，不要求落在前 30%。

分类页和店铺首页：

| 编号 | 分值 | 满分条件 |
|------|------|----------|
| ENT-11 | 40 | 至少 3 个带独立链接的商品名 |
| ENT-12 | 30 | 其中至少 1 个有价格 |
| ENT-13 | 15 | 有分类名或店铺名 |
| ENT-14 | 15 | 有品牌或店铺名 |

不足 3 个商品名时，`ENT-11` 按 `数量 / 3 × 40` 四舍五入。这项记 P1，不按单个商品缺价扣满。

### 8.3 结构清晰度，权重 20%

五项各 20 分，三类页面相同：

| 编号 | 满分条件 |
|------|----------|
| STR-01 | 可见区域恰好一个 H1 |
| STR-02 | 至少一个 H2 或 H3 |
| STR-03 | 至少一个列表或表格 |
| STR-04 | 存在 FAQ：标题含「FAQ」或「常见问题」，或有 `details`，或有定义列表 |
| STR-05 | 页面标题或 H1 与商品名、店铺名至少一方有不少于 2 个连续字符相同 |

### 8.4 Schema 有效性，权重 10%

这一维只评价**页面原有** JSON-LD，不把系统补全后的结果算进分数。

| 编号 | 分值 | 满分条件 |
|------|------|----------|
| SCH-01 | 40 | 存在可解析的 Product，且含非空 `name` |
| SCH-02 | 30 | Product 含 Offer，`price` 与 `priceCurrency` 都存在，且价格与抽到的价格一致。页面没有价格时本项记满分 |
| SCH-03 | 30 | 页面有评分时，存在 AggregateRating 的 `ratingValue`。页面没有评分时本项记满分 |

没有 Product JSON-LD 时，`SCH-01` 为 0，`SCH-02`、`SCH-03` 仍按「页面有没有价格 / 评分」决定是否满分。

系统另输出一份建议 JSON-LD，写入 `schema_json`，不参与本维打分：

1. 解析页面中的 Product。有多段时取第一段含 `name` 的 Product。
2. 用抽到的商品名、品牌、价格、货币、评分、评论数填补空字段。不覆盖页面上已有且非空的值。
3. 页面没有 Product 时，用抽到的字段新建 Product。有价格则加 Offer，有评分则加 AggregateRating。
4. 字段不足也要输出，缺什么就省略什么，不编造价格和评分。

### 8.5 技术可访问性，权重 10%

| 编号 | 分值 | 满分条件 |
|------|------|----------|
| TEC-01 | 40 | HTTP 状态 200 |
| TEC-02 | 30 | 可见文本不少于 200 字符。为 0 时记 P0 |
| TEC-03 | 15 | 响应未被 2 MB 上限截断 |
| TEC-04 | 15 | 商品名或价格若已抽到，必须出现在可见文本中，而不能只出现在脚本字符串里 |

## 9. 建议生成

模型输入仅包括：URL、页面类型、抽取字段、总分、问题 ID、前 30% 摘录（最多 4000 字符）。不发送 Cookie、请求头密钥和 API Key。

模型必须返回 JSON：

```json
{
  "description": "可放在页面前部的自包含商品描述",
  "faq": [{ "q": "问题", "a": "回答" }],
  "question_titles": ["问题式标题"]
}
```

约束：`description` 1–1200 字；`faq` 1–6 条，问和答各 1–300 字；`question_titles` 1–5 条，每条 1–80 字。不符合则视为该模型失败。

`t_scores.suggestions` 保存 JSON 文本：

```json
{
  "status": "ok",
  "description": "",
  "faq": [],
  "question_titles": [],
  "reason": null
}
```

失败时 `status` 为 `unavailable`，文案字段为空，`reason` 取 `no_model`、`model_error` 或 `invalid_output`。用户只看到「建议暂时无法生成」，看不到 `reason` 以外的供应商信息，也看不到 `reason` 本身。

模型选择：`enabled=true`，按 `priority` 从小到大。一个模型超时或输出不合法就试下一个。全部失败不改变分数。

已配置一条模型，不在文档中记录密钥明文：

| 项 | 值 |
|----|----|
| provider | `deepseek` |
| model | `deepseek-flash` |
| base_url | `https://api.deepseek.com` |
| priority | 1 |
| 调用格式 | 与 OpenAI Chat Completions 兼容 |
| 思考模式 | 关闭。建议生成要在 12 秒内结束，不使用思考模式 |

`api_key_encrypted` 是 Fernet 密文。解密密钥是环境变量 `GEO_MASTER_KEY`，只放在本地 `.env`，不进入仓库。管理接口只返回是否已配置，不返回明文。

## 10. 限额

时区 `Asia/Shanghai`。当日从本地 00:00 起算。次数只统计 `t_scores` 中已经写上的成功记录。

匿名用户同时满足两条才允许评分：

- 当日 `ip_hash` 相同的匿名记录数小于 `anonymous_daily_limit`
- 当日 `device_hash` 相同的匿名记录数小于 `anonymous_daily_limit`

任一达到上限即拒绝。这样只更换 IP 或只更换设备都不能继续免费使用。

`device_id` 由浏览器生成并放在本地存储。服务端保存 `sha256(pepper + device_id)` 到 `device_hash`。IP 保存 `sha256(pepper + ip)` 到 `ip_hash`。不存明文 IP。

登录用户只按 `user_id` 统计当日记录，不再走匿名限额。基础会员和专业会员在订阅有效时跳过次数检查。

并发请求在写入前于同一事务中重新计数。超过上限的请求不插入记录。

## 11. 账号与订阅

- 密码使用 Argon2id，只存 `password_hash`。
- 登录会话放在 HttpOnly Cookie。
- 历史接口只返回 `user_id` 等于当前用户的记录。打开历史时直接读库，不重新抓取。
- 导出只允许记录所有者。匿名请求要求先登录。

计划初始数据：

| code | 名称 | 标价 | 币种 | 周期 | 减免 | features | 行为 |
|------|------|------|------|------|------|----------|------|
| `basic` | 基础会员 | 9.90 | CNY | month | 0 | `["unlimited_score"]` | 解除每日次数限制 |
| `pro` | 专业会员 | 19.90 | CNY | month | 0 | `["unlimited_score","batch","open_api","white_label"]` | 同样不限次数；后三个权益返回未开放 |

应付金额 = 标价 − 减免金额，四舍五入到分，且必须大于 0。管理员可改标价和减免金额，不能改成非人民币或非月付。

免费层不是 `t_plans` 中的一行。没有有效订阅就是免费层。

支付渠道只有微信支付和支付宝。用户每次购买一个自然月，不签代扣协议。未配置对应渠道时，该渠道按钮不可用，计划仍展示。

支付成功后：

- 没有有效订阅时，`current_period_end` 为当前时间加 1 个自然月，`status=active`。
- 已有有效订阅时，从 `current_period_end` 再加 1 个自然月。换计划则从当前时间重新计算 1 个自然月，并改 `plan_code`。
- 下一次评分立即按新权益执行。

同一商户订单号只入账一次。取消把 `cancel_at_period_end` 设为 true，到期后改为 `canceled`，次数回到注册用户限额。到期检查在读取订阅时完成，不依赖定时任务。

## 12. 接口

统一错误体：

```json
{ "code": "QUOTA_EXCEEDED", "message": "今日免费次数已用完", "request_id": "..." }
```

常用 `code`：`INVALID_URL`、`FORBIDDEN_TARGET`、`FETCH_FAILED`、`QUOTA_EXCEEDED`、`UNAUTHENTICATED`、`NOT_FOUND`、`NOT_OPEN`、`PAYMENT_DISABLED`。

### 12.1 评分

`POST /api/v1/score`

```json
{ "url": "https://shop.example/p/1", "device_id": "客户端生成的标识" }
```

```json
{
  "id": "uuid",
  "url": "https://shop.example/p/1",
  "page_type": "product",
  "score": 72,
  "dimensions": {
    "citability": 75,
    "entity": 80,
    "structure": 60,
    "schema": 40,
    "technical": 100
  },
  "window": {
    "excerpt": "前 30% 摘录",
    "has_name": true,
    "has_price": true,
    "has_spec": false,
    "has_quotable_sentence": true
  },
  "issues": [],
  "schema_json": {},
  "suggestions": { "status": "unavailable", "description": "", "faq": [], "question_titles": [], "reason": null },
  "quota": { "limit": 3, "remaining": 2, "unlimited": false }
}
```

登录且订阅不限次数时，`unlimited` 为 `true`，`limit` 与 `remaining` 为 `null`。

`suggestions.reason` 只存在于数据库和日志，响应里去掉。

### 12.2 历史与导出

- `GET /api/v1/scores`：当前用户的记录，时间倒序。
- `GET /api/v1/scores/{id}`：所有者可读。匿名评分没有所有者，不从该接口返回。
- `GET /api/v1/scores/{id}/export.md`
- `GET /api/v1/scores/{id}/export.pdf`

导出内容与结果页一致：URL、时间、总分、五维、窗口诊断、问题、建议、Schema。

### 12.3 账号

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/me`：邮箱、角色、计划、当日剩余次数

### 12.4 订阅

- `GET /api/v1/plans`：`enabled=true` 的计划，含标价、减免金额、应付金额、币种 `CNY`、周期 `month`
- `GET /api/v1/subscription`：无有效订阅时返回免费层
- `POST /api/v1/subscription/checkout`：请求 `{ "plan_code", "provider" }`，`provider` 为 `wechat` 或 `alipay`。返回商户订单号、应付金额和支付参数（微信为二维码链接，支付宝为跳转页）
- `POST /api/v1/subscription/cancel`：只标记本期结束后不续费
- `POST /api/v1/webhook/wechat`、`POST /api/v1/webhook/alipay`：校验各自签名，不走用户会话

### 12.5 管理接口

调用者 `role` 必须是 `admin`。

- `GET/POST /admin/models`，以及启用、优先级更新
- `GET /admin/usage`：按日聚合 `t_usage_logs` 的次数和 token
- `GET/POST /admin/plans`：可改名称、标价、减免金额、启用状态。币种固定 `CNY`，周期固定 `month`
- `GET /admin/subscriptions`
- `POST /admin/subscriptions/{id}`：把状态改为 `active` 或 `expired`
- `GET/PUT /admin/settings`：只允许改 `anonymous_daily_limit` 和 `registered_daily_limit`，值为非负整数

修改次数不改历史记录。新的限制从下一次评分开始生效。

## 13. 数据模型

已建表如下。代码使用这些列名。

### geo.t_users

`id`、`email`、`password_hash`、`created_at`、`last_login`、`role`

`role` 只允许 `user`、`admin`，默认 `user`。邮箱唯一。

### geo.t_settings

`key`、`value`、`updated_at`

已有数据：`anonymous_daily_limit = 3`，`registered_daily_limit = 20`，`admin_email = "258095357@qq.com"`。次数的 `value` 是 JSON 数字，邮箱是 JSON 字符串。

### geo.t_plans

`id`、`code`、`name`、`price`、`billing_interval`、`features`、`enabled`、`currency`、`discount_amount`

`price` 是标价。`discount_amount` 是减免金额，默认 0，必须大于等于 0 且小于标价。`currency` 固定 `CNY`。`billing_interval` 固定 `month`。`code` 唯一。

已写入：`basic` 标价 9.90，`pro` 标价 19.90，减免都是 0。

### geo.t_subscriptions

`id`、`user_id`、`plan_code`、`status`、`current_period_end`、`provider`、`provider_subscription_id`、`cancel_at_period_end`、`created_at`

`status` 取 `active`、`canceled`、`expired`。`provider` 为 `wechat` 或 `alipay`。`provider_subscription_id` 存最近一笔成功支付的商户订单号。`cancel_at_period_end` 默认 false。删除用户时限制删除。`plan_code` 参照 `t_plans.code`。

### geo.t_payments

`id`、`user_id`、`plan_code`、`provider`、`out_trade_no`、`provider_trade_no`、`list_price`、`discount_amount`、`pay_amount`、`currency`、`status`、`created_at`、`paid_at`

一笔收银一条记录。`out_trade_no` 唯一。`provider` 为 `wechat` 或 `alipay`。`status` 为 `pending`、`paid`、`closed`。`pay_amount` 必须等于 `list_price - discount_amount` 且大于 0。`currency` 固定 `CNY`。支付成功才把权益写到 `t_subscriptions`。

### geo.t_scores

`id`、`url`、`score`、`dimensions`、`issues`、`suggestions`、`schema_json`、`user_id`、`ip_hash`、`device_hash`、`created_at`

`score` 为 0–100。`schema_json` 对应建议 JSON-LD。匿名记录的 `user_id` 为空。删除用户时把 `user_id` 置空，记录保留。

`dimensions` 保存五个内部整数分。`issues` 保存问题数组。窗口诊断由这些问题和当次响应中的 `window` 对象表达；历史详情从 `issues` 里编号以 `CIT-` 开头的项还原窗口结论，摘录放在 `CIT-01` 或 `CIT-11` 的 `evidence` 中。响应里的 `window` 不单独占一列。

### geo.t_model_configs

`id`、`provider`、`model`、`api_key_encrypted`、`enabled`、`priority`、`created_at`

同一 `provider + model` 唯一。`priority` 越小越优先。已有一行：`deepseek` / `deepseek-flash`，`priority=1`，`enabled=true`。密钥是 Fernet 密文。

### geo.t_usage_logs

`id`、`user_id`、`action`、`model`、`tokens`、`created_at`

`action` 取 `score` 或 `generate`。每次成功评分写一条 `score`。模型实际被调用时另写一条 `generate`，记录模型名和 token。匿名调用的 `user_id` 为空。

成本不落新列。管理页用配置中的单价乘以 token 估算，单价未配置时只显示 token。

## 14. 页面

| 页面 | 内容 |
|------|------|
| 首页 | URL 输入、评分按钮、剩余次数。匿名可直接使用 |
| 结果页 | 总分、五维雷达、窗口诊断、P0/P1 问题、可复制文案、可复制 Schema |
| 登录 / 注册 | 邮箱和密码 |
| 会员中心 | 当前计划、剩余次数、升级入口、历史列表 |
| 订阅页 | 基础会员 9.9 元/月、专业会员 19.9 元/月；有减免时同时显示标价和应付价。支付方式为微信和支付宝。专业会员的未开放权益标明未开放 |
| 模型管理 | 列表、编辑、启用、优先级。密钥只显示是否已配置 |
| 订阅管理 | 修改标价和减免金额、用户订阅筛选、手动变更状态 |
| 用量 | 调用次数、token、能算出的成本 |
| 系统设置 | 两个每日次数 |

结果页把抓取正文当文本显示，不把 HTML 插入页面。

## 15. 安全与非功能

- 抓取模块是 SSRF 边界。解析、重定向和 DNS 都要检查，禁止访问内网和元数据地址。
- 日志记录请求 ID、URL 主机名和耗时。不记录密码、API Key、Cookie 和完整 IP。
- 页面正文进入模型时只作为待分析文本。
- 单次评分目标不超过 30 秒。超过时分别看抓取、规则、模型三段，不放宽该目标。
- 只处理公开页面。

## 16. MVP 之后

顺序：无头浏览器抓取，批量 URL，白标报告，对外开放 API，其他行业规则。每项单独定范围。
