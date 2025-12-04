package com.tasystem.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 投资人账户实体
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Account {
    private String distributorId; // 销售商ID
    private String accountId;     // 基金账号 (TA账号)
    private String name;          // 投资人姓名
    private String idNo;          // 证件号码
    private String status;        // NORMAL(正常), CLOSED(销户), FROZEN(冻结)
    private LocalDateTime openTime;   // 开户时间
    private LocalDateTime updateTime; // 最后更新时间
}