"""
migration/normalize — A 形狀 dict → B 形狀 ORM 物件的純轉換函式（不碰 DB）。

★ 每個模組只負責自己那組表；全部函式都是純函式：
    輸入 = list[dict]（key 為 A 表原始欄位名），輸出 = list[<models_b 的 ORM 物件>]（未 save）。
  這樣可以不連 DB 就單元測試（直接對回傳物件的屬性 assert）。

★ 共用轉換一律重用，不重寫規則：
    - 門檻字串 → (low, high)：services.dashboard_service._parse_bounds
        單邊 '1.16'→(1.16,1.16)、雙邊 '6-9'→(6.0,9.0)、無效('-'/'N/A'/'建置中'/'')→None。
        B 的 *_status 依此判定：能解析→'valid'；原字串=='建置中'→'building'；其餘→'na'。
    - 讀值字串 → (value, status)：仿 services_b.sync_service 的分類精神
        （可重用其 _normalize_text/_parse_decimal），但來源是 VOC_SCADA_WEB.rvalue+broken，
        不是 Kepware 的 (value, quality)，故 reading 模組自建一支 rvalue→(value,status) 反解。

★ 契約：runner.py 會依下列固定簽名呼叫各模組（FK 安全順序見 runner）。實作時函式名/簽名務必一致：

  config_tables.py（多為 1:1 欄位對映）:
    normalize_source(rows)          -> list[Source]
    normalize_item(rows)            -> list[Item]
    normalize_plant(rows)           -> list[Plant]
    normalize_dept(rows)            -> list[Dept]
    normalize_mail_type(rows)       -> list[MailTypeModel]
    normalize_curve(rows)           -> list[Curve]
    normalize_acl_role(rows)        -> list[AclRole]
    normalize_acl_role_rights(rows) -> list[AclRoleRights]

  spec.py:
    normalize_spec(rows)            -> list[Spec]         # 只搬 status==1（啟用）；門檻拆 low/high+status

  reading.py:
    normalize_reading_current(rows) -> list[ReadingCurrent]   # rvalue+broken→value+status+raw_text+comm_ok；SCADA/CWMS 管制值拆欄

  isolation.py:
    normalize_isolation(closectl_rows, closectl_list_rows, ctx)
        -> tuple[list[Isolation], list[IsolationItem]]   # 只搬有效隔離；申請人改綁 ctx.personnel

  personnel.py:
    build_personnel(ctx, plant_nos)
        -> dict[str, list]  # {"employee":[...], "sign_emp":[...], "mail_list":[...], "acl_user_role":[...]}
"""
