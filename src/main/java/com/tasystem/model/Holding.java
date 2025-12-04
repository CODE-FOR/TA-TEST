package com.tasystem.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 份额持仓实体 (登记库)
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Holding {
    private String accountId;   // 基金账号
    private String fundCode;    // 基金代码
    private BigDecimal totalShares;     // 总份额
    private BigDecimal availableShares; // 可用份额
    
    // 唯一主键生成逻辑
    public static String generateKey(String accountId, String fundCode) {
        return accountId + "_" + fundCode;
    }
}