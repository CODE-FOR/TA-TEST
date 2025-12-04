package com.tasystem.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 基金净值实体
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FundNav {
    private String fundCode;
    private BigDecimal nav;
    private LocalDate date;
}