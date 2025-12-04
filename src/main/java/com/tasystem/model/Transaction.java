package com.tasystem.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 交易流水实体
 * 对应“交易监控表”
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Transaction {
    private String transId;       // 流水号
    private String distributorId; // 销售商ID
    
    // --- 看穿式交易核心字段 ---
    private String accountId;     // 投资人基金账号 (关联 Account)
    private String type;          // PURCHASE(申购), REDEEM(赎回)
    // -----------------------
    
    private String fundCode;      // 基金代码
    private BigDecimal amount;    // 申请金额 (申购用)
    private BigDecimal shares;    // 申请份额 (赎回用) / 确认份额
    
    private BigDecimal nav;       // 确认净值
    
    private String status;        // APPLIED, REPORTED_TO_MGR, CONFIRMED, REJECTED, TA_REJECTED
    private String message;       // 错误信息
}