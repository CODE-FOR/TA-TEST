package com.tasystem.repository;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.tasystem.model.Account;
import com.tasystem.model.Holding;
import lombok.extern.slf4j.Slf4j;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 业务数据仓储 (账户库 + 登记库)
 * 负责数据的持久化 (JSON Load/Dump)
 */
@Slf4j
public class TaDataRepository {

    private static final TaDataRepository INSTANCE = new TaDataRepository();
    
    // JSON文件路径
    private final String DATA_DIR = System.getenv().getOrDefault("TA_ROOT_DIR", "/app/data") + "/db";
    private final String ACCOUNT_FILE = "accounts.json";
    private final String HOLDING_FILE = "holdings.json";

    // 1. 账户库: Key = AccountId (TA账号)
    private final Map<String, Account> accountMap = new ConcurrentHashMap<>();

    // 2. 登记库: Key = AccountId_FundCode
    private final Map<String, Holding> holdingMap = new ConcurrentHashMap<>();

    private final ObjectMapper mapper;

    private TaDataRepository() {
        this.mapper = new ObjectMapper();
        this.mapper.registerModule(new JavaTimeModule());
        this.mapper.enable(SerializationFeature.INDENT_OUTPUT);
    }

    public static TaDataRepository getInstance() { return INSTANCE; }

    public Map<String, Account> getAccountMap() { return accountMap; }
    public Map<String, Holding> getHoldingMap() { return holdingMap; }

    /**
     * 系统启动时加载数据
     */
    public void loadData() {
        log.info(">>> 正在从磁盘加载业务数据 (JSON)...");
        File dir = new File(DATA_DIR);
        if (!dir.exists()) dir.mkdirs();

        // 加载账户
        try {
            File accFile = new File(dir, ACCOUNT_FILE);
            if (accFile.exists()) {
                List<Account> list = mapper.readValue(accFile, new TypeReference<List<Account>>(){});
                list.forEach(a -> accountMap.put(a.getAccountId(), a));
                log.info("   -> 已加载 {} 个账户", list.size());
            } else {
                log.warn("   -> 账户库文件不存在 (首次运行): {}", accFile.getAbsolutePath());
            }
        } catch (Exception e) {
            log.error("加载账户数据失败", e);
        }

        // 加载持仓
        try {
            File holdFile = new File(dir, HOLDING_FILE);
            if (holdFile.exists()) {
                List<Holding> list = mapper.readValue(holdFile, new TypeReference<List<Holding>>(){});
                list.forEach(h -> holdingMap.put(Holding.generateKey(h.getAccountId(), h.getFundCode()), h));
                log.info("   -> 已加载 {} 条持仓记录", list.size());
            } else {
                log.warn("   -> 登记库文件不存在 (首次运行): {}", holdFile.getAbsolutePath());
            }
        } catch (Exception e) {
            log.error("加载持仓数据失败", e);
        }
    }

    /**
     * 系统退出时落盘数据
     */
    public void dumpData() {
        log.info("<<< 正在将业务数据落盘至 JSON...");
        File dir = new File(DATA_DIR);
        if (!dir.exists()) dir.mkdirs();

        try {
            // 保存账户
            File accFile = new File(dir, ACCOUNT_FILE);
            mapper.writeValue(accFile, new ArrayList<>(accountMap.values()));
            log.info("   -> 账户数据已保存至: {}", accFile.getAbsolutePath());

            // 保存持仓
            File holdFile = new File(dir, HOLDING_FILE);
            mapper.writeValue(holdFile, new ArrayList<>(holdingMap.values()));
            log.info("   -> 持仓数据已保存至: {}", holdFile.getAbsolutePath());

        } catch (IOException e) {
            log.error("数据落盘失败", e);
        }
    }

    // --- 业务辅助方法 ---

    /**
     * 根据身份证号查找账户 (模拟简易索引)
     */
    public Account findByIdNo(String idNo) {
        return accountMap.values().stream()
                .filter(a -> idNo.equals(a.getIdNo()))
                .findFirst()
                .orElse(null);
    }
}