import type { GlobalThemeOverrides } from 'naive-ui'

const shared: GlobalThemeOverrides = {
  common: {
    fontFamily: '"IBM Plex Sans", "Noto Sans SC", "PingFang SC", sans-serif',
    borderRadius: '6px',
    borderRadiusSmall: '5px',
    heightMedium: '34px',
  },
  Button: { heightMedium: '34px', paddingMedium: '0 14px' },
  Card: { borderRadius: '8px', paddingMedium: '16px' },
  DataTable: { thPaddingMedium: '9px 12px', tdPaddingMedium: '8px 12px', tdColorHover: 'rgba(91, 128, 102, .06)' },
  Descriptions: { thPadding: '10px 12px', tdPadding: '10px 12px' },
  Progress: { railHeight: '7px', railBorderRadius: '2px', fillBorderRadius: '2px' },
  Tag: { borderRadius: '5px' },
}

export const lightThemeOverrides: GlobalThemeOverrides = {
  ...shared,
  common: {
    ...shared.common,
    primaryColor: '#397259',
    primaryColorHover: '#2f624b',
    primaryColorPressed: '#285540',
    successColor: '#397259',
    warningColor: '#9a681d',
    errorColor: '#b34848',
    infoColor: '#5c6e63',
    bodyColor: '#f7f8f6',
    cardColor: '#ffffff',
    modalColor: '#ffffff',
    popoverColor: '#ffffff',
    tableColor: '#ffffff',
    textColorBase: '#252923',
    textColor1: '#252923',
    textColor2: '#4f5750',
    textColor3: '#727a73',
    borderColor: '#d9dad4',
    dividerColor: '#e1e2dc',
  },
}

export const softThemeOverrides: GlobalThemeOverrides = {
  ...lightThemeOverrides,
  common: {
    ...lightThemeOverrides.common,
    bodyColor: '#f1efe8',
    cardColor: '#fbfaf5',
    modalColor: '#fbfaf5',
    popoverColor: '#fffef9',
    tableColor: '#fbfaf5',
    borderColor: '#d9d4c8',
    dividerColor: '#e3ded2',
  },
}

export const darkThemeOverrides: GlobalThemeOverrides = {
  ...shared,
  common: {
    ...shared.common,
    primaryColor: '#7fb18d',
    primaryColorHover: '#94c19f',
    primaryColorPressed: '#6b9d79',
    successColor: '#7fb18d',
    warningColor: '#d5a95f',
    errorColor: '#dc7777',
    infoColor: '#91a096',
    bodyColor: '#111412',
    cardColor: '#1a1e1b',
    modalColor: '#1a1e1b',
    popoverColor: '#222723',
    tableColor: '#1a1e1b',
    textColorBase: '#edf0ed',
    textColor1: '#edf0ed',
    textColor2: '#c2c9c3',
    textColor3: '#8d978f',
    borderColor: '#303731',
    dividerColor: '#303731',
  },
}
