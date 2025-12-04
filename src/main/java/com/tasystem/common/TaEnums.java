package com.tasystem.common;

/**
 * 全局枚举定义
 */
public class TaEnums {

    /**
     * 系统批次阶段
     * 只有阶段1全部完成后，才能进入阶段2
     */
    public enum SystemPhase {
        BATCH_1_APPLY,   // 待确认批次 (处理申请、净值)
        BATCH_2_CONFIRM  // 确认批次 (处理确认回执)
    }

    /**
     * 任务/文件处理状态流转
     */
    public enum TaskStatus {
        WAITING_FILE,       // 等待物理文件
        FILE_RECEIVED,      // 文件已到达
        READY_TO_PROCESS,   // 依赖满足
        PROCESSING,         // 处理中
        PROCESSED,          // 完成
        FAILED              // 失败
    }

    /**
     * 文件业务类型
     */
    public enum FileType {
        MGR_NAV,            // [阶段1] 管理人-净值
        DIST_ACC,           // [阶段1] 销售商-账户
        DIST_TRADE,         // [阶段1] 销售商-交易
        
        MGR_CONFIRM         // [阶段2] 管理人-确认
    }
}