import { useId, useState } from "react";
import type { DragEvent } from "react";
import type { GrossNet, UploadInput } from "../../api/queries";
import { CURRENCIES } from "../../state/currency";
import type { Currency } from "../../state/currency";

export interface TrackRecordInputProps {
  /** An upload is running. */
  busy: boolean;
  onRun: (input: UploadInput) => void;
}

const FEES: readonly (readonly [GrossNet, string])[] = [
  ["", "Not stated"],
  ["net", "Net"],
  ["gross", "Gross"],
];

const NEED_FILE = "Choose a CSV file first.";

/**
 * The track-record controls in the sidebar: a drop zone for the CSV (a native file input laid over
 * the zone, so click, keyboard and drag and drop all work), a name, the fee basis and the currency
 * of the record as segmented controls like the date range, and the run button. The file is sent to the server and held there in
 * memory for the one request only; this component never reads it.
 */
export function TrackRecordInput({ busy, onRun }: TrackRecordInputProps) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [grossNet, setGrossNet] = useState<GrossNet>("");
  const [recordCurrency, setRecordCurrency] = useState<Currency>("USD");
  const [over, setOver] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const hintId = useId();

  const choose = (next: File | null) => {
    setFile(next);
    setMessage(null);
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setOver(false);
    choose(event.dataTransfer.files[0] ?? null);
  };

  return (
    <form
      className="controls"
      aria-label="Track record controls"
      onSubmit={(event) => {
        event.preventDefault();
        if (file === null) {
          setMessage(NEED_FILE);
          return;
        }
        onRun({ file, name, grossNet, recordCurrency });
      }}
    >
      <div className="side-group">
        <label
          className={over ? "ctl-drop over" : file ? "ctl-drop chosen" : "ctl-drop"}
          onDragOver={(event) => {
            event.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
        >
          <input
            type="file"
            name="file"
            accept=".csv,text/csv"
            aria-describedby={hintId}
            onChange={(event) => choose(event.target.files?.[0] ?? null)}
          />
          <span>{file ? file.name : "Drop a CSV file here, or choose one"}</span>
        </label>
        <p className="side-note" id={hintId}>
          Two columns, date and return: one decimal return per month, for example 2021-01-31,0.012. At least 36
          months. The file is analysed in memory and not stored.
        </p>
      </div>
      <div className="side-group">
        <div className="ctl-name">
          <label className="side-label" htmlFor="track-name">
            Name
          </label>
          <input
            id="track-name"
            type="text"
            autoComplete="off"
            maxLength={80}
            placeholder="Uploaded track record"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </div>
        <fieldset className="ctl-range">
          <legend className="side-label">Returns are</legend>
          <span className="seg-range">
            {FEES.map(([value, label]) => (
              <label key={value} className="seg-opt">
                <input
                  type="radio"
                  name="gross-net"
                  value={value}
                  checked={grossNet === value}
                  onChange={() => setGrossNet(value)}
                />
                <span>{label}</span>
              </label>
            ))}
          </span>
        </fieldset>
        <fieldset className="ctl-range">
          <legend className="side-label">Record is in</legend>
          <span className="seg-range">
            {CURRENCIES.map((value) => (
              <label key={value} className="seg-opt">
                <input
                  type="radio"
                  name="record-currency"
                  value={value}
                  checked={recordCurrency === value}
                  onChange={() => setRecordCurrency(value)}
                />
                <span>{value}</span>
              </label>
            ))}
          </span>
        </fieldset>
        <button type="submit" className="btn" disabled={busy}>
          Factor it
        </button>
        {message !== null ? (
          <p className="ctl-err" role="alert">
            {message}
          </p>
        ) : null}
      </div>
      <span className="vh" role="status">
        {busy ? "Analysing the track record." : ""}
      </span>
    </form>
  );
}
