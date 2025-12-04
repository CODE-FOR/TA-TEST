package com.tasystem.model;

import com.tasystem.common.TaEnums.FileType;
import com.tasystem.common.TaEnums.TaskStatus;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 监控任务实体
 * 对应“文件收发监控表”中的一行记录
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MonitorTask {

    // --- 基础信息 ---
    private String taskId;           // 任务唯一标识 (主键)
    private FileType fileType;       // 文件类型
    private String senderId;         // 发送方ID (管理人ID 或 销售商ID)
    private String expectedFileName; // 预期接收的文件名 (根据排程生成)
    
    // --- 运行时状态 ---
    private TaskStatus status;       // 当前状态
    private String fullPath;         // 实际接收到的物理文件路径
    private String message;          // 处理结果信息
    
    // --- 关键依赖约束 ---
    
    /**
     * 强依赖的前置任务ID
     * 例如：交易文件依赖账户文件先处理完成
     */
    private String dependencyTaskId;

    /**
     * 业务数据依赖
     * 例如：交易文件依赖该 FundCode 对应的净值是否已更新
     */
    private String relatedFundCode;
}