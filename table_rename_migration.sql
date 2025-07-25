-- job_required_skills 테이블을 job_roles로 이름 변경
-- 이 SQL문은 PostgreSQL에서 실행되어야 합니다.

-- 1. 테이블명 변경
ALTER TABLE job_required_skills RENAME TO job_roles;

-- 2. 외래키 제약조건 확인 및 업데이트 (필요한 경우)
-- job_posts 테이블의 job_required_skill_id 컬럼이 job_roles.id를 참조하도록 유지
-- (컬럼명은 그대로 두고 참조 테이블명만 변경됨)

-- 3. 인덱스명 업데이트 (필요한 경우)
-- 기존 인덱스들이 새 테이블명을 반영하도록 업데이트할 수 있습니다.
-- 예: ALTER INDEX job_required_skills_pkey RENAME TO job_roles_pkey;

-- 4. 시퀀스명 업데이트 (필요한 경우)  
-- 기본키의 시퀀스명도 업데이트할 수 있습니다.
-- 예: ALTER SEQUENCE job_required_skills_id_seq RENAME TO job_roles_id_seq;

-- 확인용 쿼리
-- 테이블이 정상적으로 이름이 변경되었는지 확인
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('job_required_skills', 'job_roles');

-- 외래키 관계 확인
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
AND (ccu.table_name = 'job_roles' OR tc.table_name LIKE '%job%'); 