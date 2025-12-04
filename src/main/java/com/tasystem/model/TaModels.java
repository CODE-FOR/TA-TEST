package com.tasystem.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class TaModels {

    public enum TaskStatus {
        WAITING_FILE,       // 1. 等待文件到达 (物理文件不存在)
        FILE_RECEIVED,      // 2. 文件已到达 (物理文件存在，等待依赖)
        READY_TO_PROCESS,   // 3. 依赖满足，准备处理 (进入线程池队列)
        PROCESSING,         // 4. 处理中
        PROCESSED,          // 5. 处理完成
        FAILED              // X. 失败
    }

    public enum FileType {
        MGR_NAV,            // 管理人-净值
        MGR_CONFIRM,        // 管理人-确认
        DIST_ACC,           // 销售商-账户申请
        DIST_TRADE          // 销售商-交易申请
    }

    // --- 监控表中的任务单元 ---
    @Data @Builder @NoArgsConstructor @AllArgsConstructor
    public static class MonitorTask {
        private String taskId;          // 唯一任务ID (例: DIST01_TRADE_20231027)
        private String expectedFileName;// 期望的文件名
        private FileType fileType;
        private String senderId;        // 来源 (管理人ID 或 销售商ID)
        private TaskStatus status;
        
        // 依赖控制
        private String dependencyTaskId; // 强依赖的任务ID (例如: 交易依赖账户，或者依赖净值)
        private String relatedFundCode;  // 关联基金代码 (用于交易关联行情)
        
        private String fullPath;         // 实际存储路径 (运行时填充)
    }

    // --- 业务实体 ---
    @Data @Builder @NoArgsConstructor @AllArgsConstructor
    public static class Transaction {
        private String transId;
        private String fundCode;
        private BigDecimal amount;
        private String status;
    }

    @Data @Builder @NoArgsConstructor @AllArgsConstructor
    public static class FundNav {
        private String fundCode;
        private BigDecimal nav;
    }

    // --- 核心监控表仓库 (Singleton) ---
    public static class MonitorRepository {
        private static final MonitorRepository INSTANCE = new MonitorRepository();
        
        // 1. 管理人文件监控表 (List保持加入顺序，模拟预设清单)
        private final List<MonitorTask> managerMonitor = new ArrayList<>();
        
        // 2. 销售机构文件监控表
        private final List<MonitorTask> distributorMonitor = new ArrayList<>();
        
        // 3. 交易流水监控
        private final Map<String, Transaction> tradeMonitor = new ConcurrentHashMap<>();
        
        // 内存中的净值表
        private final Map<String, FundNav> navTable = new ConcurrentHashMap<>();

        private MonitorRepository() {}
        public static MonitorRepository getInstance() { return INSTANCE; }

        public List<MonitorTask> getManagerMonitor() { return managerMonitor; }
        public List<MonitorTask> getDistributorMonitor() { return distributorMonitor; }
        public Map<String, Transaction> getTradeMonitor() { return tradeMonitor; }
        public Map<String, FundNav> getNavTable() { return navTable; }

        // --- 初始化每日计划 (模拟) ---
        // 实际场景中，这里应该读取配置数据库或配置文件
        public void initDailySchedule() {
            String today = LocalDate.now().toString().replace("-", ""); // 20231027
            
            System.out.println(">>> 初始化今日(" + today + ")任务排程表...");

            // 1. 计划：接收管理人净值 (基金A, 基金B)
            managerMonitor.add(MonitorTask.builder()
                    .taskId("NAV_FUND_A")
                    .fileType(FileType.MGR_NAV)
                    .expectedFileName("NAV_FUND_A_" + today + ".csv")
                    .relatedFundCode("FUND_A")
                    .status(TaskStatus.WAITING_FILE).build());
            
            managerMonitor.add(MonitorTask.builder()
                    .taskId("NAV_FUND_B")
                    .fileType(FileType.MGR_NAV)
                    .expectedFileName("NAV_FUND_B_" + today + ".csv")
                    .relatedFundCode("FUND_B")
                    .status(TaskStatus.WAITING_FILE).build());

            // 2. 计划：接收销售商 (DIST_01) 的文件
            // 2.1 账户文件 (无依赖)
            String accTaskId = "DIST01_ACC";
            distributorMonitor.add(MonitorTask.builder()
                    .taskId(accTaskId)
                    .senderId("DIST_01")
                    .fileType(FileType.DIST_ACC)
                    .expectedFileName("DIST01_ACC_" + today + ".csv")
                    .status(TaskStatus.WAITING_FILE).build());
            
            // 2.2 交易文件 - 基金A (依赖账户文件完成 + 基金A净值完成)
            // 注意：这里我们演示“双重依赖”在编排器中的处理。
            // 逻辑上：交易依赖同机构的账户处理完毕 (顺序性)，同时也依赖净值。
            distributorMonitor.add(MonitorTask.builder()
                    .taskId("DIST01_TRADE_A")
                    .senderId("DIST_01")
                    .fileType(FileType.DIST_TRADE)
                    .expectedFileName("DIST01_TRADE_FUND_A_" + today + ".csv")
                    .dependencyTaskId(accTaskId) // 显式依赖账户文件
                    .relatedFundCode("FUND_A")   // 隐式依赖行情
                    .status(TaskStatus.WAITING_FILE).build());

            // 3. 计划：确认批次 - 管理人确认文件
            managerMonitor.add(MonitorTask.builder()
                    .taskId("CONFIRM_DATA")
                    .fileType(FileType.MGR_CONFIRM)
                    .expectedFileName("CONFIRM_" + today + ".csv")
                    .status(TaskStatus.WAITING_FILE).build());
        }
    }
}