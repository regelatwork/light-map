import { GLOBALCONFIG_METADATA } from '../../types/schema.generated';
import type { GlobalConfig, FieldMetadata } from '../../types/schema.generated';

interface BaseProps<T> {
  name: keyof T;
  config: T;
  update: (val: Partial<T>) => void;
  metadata: Record<keyof T, FieldMetadata>;
}

export function ConfigNumberInput<T>({ name, config, update, metadata }: BaseProps<T>) {
  const meta = metadata[name];
  const value = (config[name] as unknown as number) ?? meta.default ?? 0;

  return (
    <div className="p-4 bg-gray-50 rounded-xl border border-gray-100 space-y-3">
      <div className="flex justify-between items-center">
        <label className="text-sm font-bold text-gray-700 uppercase tracking-wider">{meta.title}</label>
      </div>
      <div className="flex gap-4 items-center">
        <input
          type="number"
          value={value}
          min={meta.min}
          max={meta.max}
          step={meta.step ?? (meta.min !== undefined && meta.min % 1 !== 0 ? "0.1" : "1")}
          onChange={(e) => update({ [name]: parseFloat(e.target.value) } as any)}
          className="flex-1 px-4 py-2 text-sm border-2 border-gray-200 rounded-lg focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all outline-none bg-white font-medium text-black"
        />
        {meta.title.includes('(mm)') && <span className="text-sm text-gray-500 font-medium">mm</span>}
      </div>
      {meta.description && <p className="text-xs text-gray-500">{meta.description}</p>}
    </div>
  );
}

export function ConfigCheckbox<T>({ name, config, update, metadata }: BaseProps<T>) {
  const meta = metadata[name];
  const checked = (config[name] as unknown as boolean) ?? meta.default ?? false;

  return (
    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100">
      <div>
        <h4 className="font-bold text-gray-800">{meta.title}</h4>
        {meta.description && <p className="text-sm text-gray-500">{meta.description}</p>}
      </div>
      <button
        onClick={() => update({ [name]: !checked } as any)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
          checked ? 'bg-blue-600' : 'bg-gray-200'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}

export function ConfigSelect<T>({ name, config, update, metadata }: BaseProps<T>) {
  const meta = metadata[name];
  const value = (config[name] as unknown as string) ?? meta.default ?? "";

  return (
    <div className="p-4 bg-gray-50 rounded-xl border border-gray-100 space-y-3">
      <div className="flex justify-between items-center">
        <label className="text-sm font-bold text-gray-700 uppercase tracking-wider">{meta.title}</label>
      </div>
      <select
        value={value}
        onChange={(e) => update({ [name]: e.target.value } as any)}
        className="w-full px-4 py-2 text-sm border-2 border-gray-200 rounded-lg focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all outline-none bg-white font-medium text-black"
      >
        {meta.options?.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {meta.description && <p className="text-xs text-gray-500">{meta.description}</p>}
    </div>
  );
}

// Specialized component for GlobalConfig to save typing the metadata prop every time
export const GlobalConfigNumber = (props: Omit<BaseProps<GlobalConfig>, 'metadata'>) => (
  <ConfigNumberInput {...props} metadata={GLOBALCONFIG_METADATA} />
);

export const GlobalConfigCheckbox = (props: Omit<BaseProps<GlobalConfig>, 'metadata'>) => (
  <ConfigCheckbox {...props} metadata={GLOBALCONFIG_METADATA} />
);

export const GlobalConfigSelect = (props: Omit<BaseProps<GlobalConfig>, 'metadata'>) => (
  <ConfigSelect {...props} metadata={GLOBALCONFIG_METADATA} />
);
