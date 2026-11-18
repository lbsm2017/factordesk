/** Named aliases over the generated OpenAPI types; the rest of the app imports from here. */
import type { components } from "./types.gen";

type Schemas = components["schemas"];

export type FactorReport = Schemas["FactorReport"];
export type ApiError = Schemas["ApiError"];
export type ErrorCode = ApiError["code"];
export type FactorDataStatus = Schemas["FactorDataStatus"];
export type TickerSuggestion = Schemas["TickerSuggestion"];
export type TickerSuggestions = Schemas["TickerSuggestions"];
export type RangeOption = Schemas["RangeOption"];
export type RangeOptions = Schemas["RangeOptions"];
export type RangePreset = RangeOption["preset"];

export type Regression = Schemas["Regression"];
export type FactorStat = Schemas["FactorStat"];
export type RollingWindow = Schemas["RollingWindow"];
export type AverageBetaPanel = Schemas["AverageBetaPanel"];
export type AverageBeta = Schemas["AverageBeta"];
export type ReturnContribution = Schemas["ReturnContribution"];
export type RiskContribution = Schemas["RiskContribution"];
export type RiskFactorDetail = Schemas["RiskFactorDetail"];
export type ResidualDiagnostics = Schemas["ResidualDiagnostics"];
export type QualityGate = Schemas["QualityGate"];
export type MultiDayRegression = Schemas["MultiDayRegression"];
export type PriceSeries = Schemas["PriceSeries"];
export type DataInfo = Schemas["DataInfo"];
export type ReportWarning = Schemas["ReportWarning"];
export type AuditFinding = Schemas["AuditFinding"];

/** Canonical factor names and order (backend FACTOR_NAMES). */
export const FACTOR_NAMES = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"] as const;
export type FactorName = (typeof FACTOR_NAMES)[number];
