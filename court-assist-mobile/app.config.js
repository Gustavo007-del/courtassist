module.exports = ({ config }) => {
  const apiUrl = process.env.EXPO_PUBLIC_API_URL || '';
  const release = process.env.COURT_ASSIST_RELEASE === '1';
  if (release) {
    const url = URL.canParse(apiUrl) ? new URL(apiUrl) : null;
    if (!url || url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) {
      throw new Error('Release builds require an HTTPS EXPO_PUBLIC_API_URL without credentials or query parameters.');
    }
  }
  const allowHttp = !release && process.env.COURT_ASSIST_ALLOW_HTTP_DEV === '1' && apiUrl.startsWith('http://');
  return {
    ...config,
    android: { ...config.android, ...(process.env.GOOGLE_SERVICES_FILE ? {googleServicesFile:process.env.GOOGLE_SERVICES_FILE} : {}) },
    plugins: config.plugins.map((plugin) => plugin === 'expo-build-properties'
      ? ['expo-build-properties', { android: { usesCleartextTraffic: allowHttp } }]
      : plugin),
  };
};
