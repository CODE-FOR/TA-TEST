package com.tasystem.repository;

import com.tasystem.common.TaEnums.FileType;
import com.tasystem.common.TaEnums.TaskStatus;
import com.tasystem.model.FundNav;
import com.tasystem.model.MonitorTask;
import com.tasystem.model.Transaction;
import lombok.extern.slf4j.Slf4j;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 监控表仓储 (Singleton模式)
 * 负责存储所有任务状态、交易数据，并在启动时初始化当日任务排程。
 */
@Slf4j
public class MonitorRepository {

    private static final MonitorRepository INSTANCE = new MonitorRepository();

    // 1. 管理人文件收发监控表 (预设任务清单)
    private final List<MonitorTask> managerTaskTable = new ArrayList<>();

    // 2. 销售商文件收发监控表 (预设任务清单)
    private final List<MonitorTask> distributorTaskTable = new ArrayList<>();

    // 3. 交易监控表 (Key: TransId)
    private final Map<String, Transaction> transactionTable = new ConcurrentHashMap<>();

    // 4. 内存净值表 (Key: FundCode) - 用于快速依赖校验
    private final Map<String, FundNav> navTable = new ConcurrentHashMap<>();

    private MonitorRepository() {}

    public static MonitorRepository getInstance() {
        return INSTANCE;
    }

    public List<MonitorTask> getManagerTaskTable() { return managerTaskTable; }
    public List<MonitorTask> getDistributorTaskTable() { return distributorTaskTable; }
    public Map<String, Transaction> getTransactionTable() { return transactionTable; }
    public Map<String, FundNav> getNavTable() { return navTable; }

    /**
     * 核心方法：初始化每日任务排程
     * 这里预定义了系统今天“应该”收到的所有文件，无论它们是否已经物理到达。
     */
    public void initDailySchedule() {
        String todayStr = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        log.info(">>> 开始初始化 [{}] 任务排程表...", todayStr);

        // --- Step 1: 计划接收管理人的净值文件 (基金01, 基金02) ---
        managerTaskTable.add(createTask("MGR_NAV_01", FileType.MGR_NAV, "MANAGER", 
                "NAV_FUND01_" + todayStr + ".csv", null, "FUND01"));
        
        managerTaskTable.add(createTask("MGR_NAV_02", FileType.MGR_NAV, "MANAGER", 
                "NAV_FUND02_" + todayStr + ".csv", null, "FUND02"));

        // --- Step 2: 计划接收销售商(DIST_A)的文件 ---
        // 2.1 账户文件 (无前置依赖)
        String distA_Acc_Id = "DIST_A_ACC";
        distributorTaskTable.add(createTask(distA_Acc_Id, FileType.DIST_ACC, "DIST_A", 
                "DIST_A_ACC_" + todayStr + ".csv", null, null));

        // 2.2 交易文件 - FUND01 (依赖：账户文件 + FUND01净值)
        distributorTaskTable.add(createTask("DIST_A_TRADE_01", FileType.DIST_TRADE, "DIST_A",
                "DIST_A_TRADE_FUND01_" + todayStr + ".csv", 
                distA_Acc_Id, // 显式任务依赖
                "FUND01"));   // 业务数据依赖

        // 2.3 交易文件 - FUND02 (依赖：账户文件 + FUND02净值)
        distributorTaskTable.add(createTask("DIST_A_TRADE_02", FileType.DIST_TRADE, "DIST_A",
                "DIST_A_TRADE_FUND02_" + todayStr + ".csv", 
                distA_Acc_Id, 
                "FUND02"));

        // --- Step 3: 计划接收管理人的确认文件 (确认批次) ---
        managerTaskTable.add(createTask("MGR_CONFIRM", FileType.MGR_CONFIRM, "MANAGER", 
                "CONFIRM_" + todayStr + ".csv", null, null));

        log.info(">>> 任务排程初始化完成。管理人任务数: {}, 销售商任务数: {}", 
            managerTaskTable.size(), distributorTaskTable.size());
    }

    private MonitorTask createTask(String id, FileType type, String sender, String fileName, String depId, String fundCode) {
        return MonitorTask.builder()
                .taskId(id)
                .fileType(type)
                .senderId(sender)
                .expectedFileName(fileName)
                .dependencyTaskId(depId)
                .relatedFundCode(fundCode)
                .status(TaskStatus.WAITING_FILE) // 初始状态均为等待文件
                .build();
    }
    
    public MonitorTask findTaskById(String taskId) {
        for (MonitorTask t : distributorTaskTable) {
            if (t.getTaskId().equals(taskId)) return t;
        }
        for (MonitorTask t : managerTaskTable) {
            if (t.getTaskId().equals(taskId)) return t;
        }
        return null;
    }
}