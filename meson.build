project('modem-tuner', version: '1.0.0', meson_version: '>=0.62')

appid = 'io.github.modemtuner.ModemTuner'

prefix = get_option('prefix')
bindir = get_option('bindir')
libdir = get_option('libdir')
datadir = get_option('datadir')

gnome = import('gnome')

install_subdir(
  'src/modem_tuner',
  install_dir: libdir / 'modem-tuner',
  exclude_directories: ['__pycache__'],
)

install_data(
  'data/modem-tuner',
  install_dir: bindir,
  install_mode: 'rwxr-xr-x',
)

conf = configuration_data()
conf.set('BINDIR', prefix / bindir)

configure_file(
  input: 'data' / (appid + '.desktop.in'),
  output: appid + '.desktop',
  configuration: conf,
  install_dir: datadir / 'applications',
)

install_data(
  'data' / (appid + '.metainfo.xml'),
  install_dir: datadir / 'metainfo',
)

install_data(
  'data' / (appid + '.svg'),
  install_dir: datadir / 'icons/hicolor/scalable/apps',
)

gnome.post_install(
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
