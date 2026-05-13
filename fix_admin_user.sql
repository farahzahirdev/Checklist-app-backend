-- Fix admin@example.com user directly in database
-- This script:
-- 1. Sets the user's role to 'admin'
-- 2. Removes invalid role assignments
-- 3. Assigns the admin role properly

BEGIN;

-- Step 1: Find and verify the admin user
SELECT 'Step 1: Finding admin@example.com user' AS step;
SELECT id, email, role, is_active FROM users WHERE email = 'admin@example.com';

-- Step 2: Update the user's role to 'admin'
UPDATE users 
SET role = 'admin'
WHERE email = 'admin@example.com';

SELECT 'Step 2: Updated role to admin' AS step;

-- Step 3: Remove all current role assignments for this user
DELETE FROM user_role_assignments 
WHERE user_id = (SELECT id FROM users WHERE email = 'admin@example.com');

SELECT 'Step 3: Removed all role assignments' AS step;

-- Step 4: Assign the admin role from the roles table
INSERT INTO user_role_assignments (user_id, role_id, assigned_by_user_id, created_at, updated_at)
SELECT 
    u.id as user_id,
    r.id as role_id,
    u.id as assigned_by_user_id,
    NOW() as created_at,
    NOW() as updated_at
FROM users u
CROSS JOIN roles r
WHERE u.email = 'admin@example.com'
  AND r.code = 'admin';

SELECT 'Step 4: Assigned admin role' AS step;

-- Step 5: Verify the fix
SELECT 'Step 5: Verifying the fix' AS step;
SELECT 
    u.id,
    u.email,
    u.role,
    u.is_active,
    COUNT(ura.role_id) as role_count,
    STRING_AGG(r.code, ', ') as roles
FROM users u
LEFT JOIN user_role_assignments ura ON u.id = ura.user_id
LEFT JOIN roles r ON ura.role_id = r.id
WHERE u.email = 'admin@example.com'
GROUP BY u.id, u.email, u.role, u.is_active;

SELECT 'Fix complete! User should now have admin role.' AS result;

COMMIT;
