/** Named aliases over the generated OpenAPI types; the rest of the app imports from here. */
import type { components } from "./types.gen";

type Schemas = components["schemas"];

export type FactorReport = Schemas["FactorReport"];
export type ApiError = Schemas["ApiError"];
export type ErrorCode = ApiError["code"];
/** The server-sent events of the three `.../stream` report endpoints (generated from the backend schema). */
export type ProgressStep = Schemas["ProgressStep"];
export type ProgressStepId = ProgressStep["step"];
export type ApiErrorEvent = Schemas["ApiErrorEvent"];
export type FactorDataStatus = Schemas["FactorDataStatus"];
export type TickerSuggestion = Schemas["TickerSuggestion"];
export type TickerSuggestions = Schemas["TickerSuggestions"];
export type AssetClassLibrary = Schemas["AssetClassLibrary"];
export type LibraryLine = Schemas["LibraryLine"];
export type CurrencyInfo = Schemas["CurrencyInfo"];
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
export type SampleInfo = Schemas["SampleInfo"];

/** Optional sections of the schema v3 contract (docs/specs/schema-v3-contract.md); null when not computed. */
export type PerformanceSection = Schemas["PerformanceSection"];
export type TailRiskSection = Schemas["TailRiskSection"];
export type LeadLagSection = Schemas["LeadLagSection"];
export type ShrunkBetas = Schemas["ShrunkBetas"];
export type FragilitySection = Schemas["FragilitySection"];
export type ResidualAnalysis = Schemas["ResidualAnalysis"];
export type KalmanBetaSeries = Schemas["KalmanBetaSeries"];
export type WorldBetaSection = Schemas["WorldBetaSection"];
export type AlphaStrip = Schemas["AlphaStrip"];
export type AlphaStripRow = Schemas["AlphaStripRow"];
export type PortfolioBacktestSection = Schemas["PortfolioBacktestSection"];
export type HoldingsSection = Schemas["HoldingsSection"];
export type HoldingRow = Schemas["HoldingRow"];
export type TargetWeightRow = Schemas["TargetWeightRow"];
export type MacroSection = Schemas["MacroSection"];
export type MacroRow = Schemas["MacroRow"];
export type EnergySection = Schemas["EnergySection"];
export type EnergyModel = Schemas["EnergyModel"];
export type EnergyRow = Schemas["EnergyRow"];

/** Canonical factor names and order: the five of FF5 (backend FACTOR_NAMES), then Mom, the sixth factor of FF6. */
export const FACTOR_NAMES = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"] as const;
export type FactorName = (typeof FACTOR_NAMES)[number];
