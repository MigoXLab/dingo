from typing import List


def get_xyz_head_word(lang) -> List[str]:
    return xyz_head_word[lang]


xyz_head_word = {
    'ar': [
        'المصدر',  # source
        'دار نشر',  # publish
        'مراجع',  # reference
    ],
    'ru': [
        'Российское информационное агентство',
        'РИА Новости',  # Russian News Agency
        'Информационное телеграфное агентство России',
        'ИТАР-ТАСС',
        'TASS',  # TASS
        'Международное информационное агентство «Интерфакс»',
        'Интерфакс',
        'Interfax',  # Interfax
        'Спутник новостной портал',
        'Спутник',
        'Sputnik International',
        'Sputnik',  # Sputnik
        'Русия Аль-Яум',
        'Россия сегодня',
        'Эксмо',
        'Eksmo',  # publish
        'Просвещение',
        'AST',  # publish
        'Просвещение',
        'Prosvechtchénié',  # Enlightenment Publishing Housepublish
        'Дрофа',
        'Drofa',  # Drofa publish
        'Олма Медиа Групп',
        'Olma Media Group'  # Olma Media Group publish
        'Фото',  # photo
        'Источник',  # source
        'Иллюстрированное',  # illustrations
    ],
    'ko': [
        '그림출처',  # photo
        '출처',  # source
        '사진=MBC',  # phote from MBC
        '사진=',  # pic
        '저작권자 ©',  # copyright
        '최경민',  # copyright
        r'\(취재원',  # reporter
        '사진 출처',  # photo source
        '촬영 날짜',  # photo data
        'faluninfo.or.kr',  # flg web
        '인턴기자',  # intern reporter
        '넷플릭스 제공',  # Netflix
        '컬버시티=AP 연합뉴스',  # AP
        '트위터 캡쳐',  # Teitter screenshot
    ],
    'th': ['รูปภาพ', 'การถ่ายภาพ', 'แหล่งที่มา', 'หนังสือภาพประกอบ'],  # picture  # photo  # source  # illustrations
    'vi': [
        'Hình ảnh',  # photo
        'Nguồn',
        'nguồn'  # source
        'Liên kết ngoài',  # link
        'Chú thích',  # reference
    ],
    'cs': ['Obrázek', 'Ftografování', 'Zdroj', 'Ilustrovaná kniha'],  # picture  # photo  # source  # illustrations
    'hu': [
        'Foto:',
        'Fénykép:',
        'Kép:',  # picture
        'Fényképezés',  # photo
        'Források',
        'Forrás',  # source
    ],
    'sr': ['илустрација', 'извор', 'Референце'],  # photo  # source  # reference
}
